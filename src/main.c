// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/usb.h>
#include <linux/input.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/workqueue.h>

#define XPPEN_VENDOR 0x28bd
#define XPPEN_PRODUCT 0x0932
#define PEN_REPORT 7
#define PEN_REPORT_SIZE 10

struct pen_state {
	int x, y;
	int remainder_x, remainder_y;
	bool valid;
};

struct mouse_frame {
	int dx, dy;
	bool left, right;
};

static void pen_reset(struct pen_state *state)
{
	*state = (struct pen_state){ 0 };
}

static bool pen_decode(struct pen_state *state, const unsigned char *data,
		       size_t length, unsigned int scale, struct mouse_frame *frame)
{
	int x, y, total_x, total_y;

	if (length != PEN_REPORT_SIZE || data[0] != PEN_REPORT ||
	    scale < 1 || scale > 1024)
		return false;
	/* Exit packets may contain undefined coordinates. Always release buttons. */
	if (!(data[1] & 0x20)) {
		pen_reset(state);
		*frame = (struct mouse_frame){ 0 };
		return true;
	}
	x = data[2] | ((unsigned int)data[3] << 8);
	y = data[4] | ((unsigned int)data[5] << 8);
	if (x > 32767 || y > 32767)
		return false;
	*frame = (struct mouse_frame){ .left = !!(data[1] & 1),
				     .right = !!(data[1] & 2) };
	if (state->valid) {
		total_x = x - state->x + state->remainder_x;
		total_y = y - state->y + state->remainder_y;
		frame->dx = total_x / (int)scale;
		frame->dy = total_y / (int)scale;
		state->remainder_x = total_x % (int)scale;
		state->remainder_y = total_y % (int)scale;
	}
	state->x = x;
	state->y = y;
	state->valid = true;
	return true;
}

static unsigned int divisor = 8;
module_param(divisor, uint, 0444);
MODULE_PARM_DESC(divisor, "Movement divisor, 1..1024 (default 8)");

struct xppen_mouse {
	struct usb_device *udev;
	struct usb_interface *interface;
	struct input_dev *input;
	struct urb *urb;
	unsigned char *buffer;
	dma_addr_t dma;
	unsigned int buffer_size;
	unsigned int pipe;
	spinlock_t lock;
	struct work_struct recover;
	struct pen_state pen;
	bool running;
};

/* Called under lock, or after the URB and worker have both been drained. */
static void xppen_release(struct xppen_mouse *mouse)
{
	pen_reset(&mouse->pen);
	input_report_key(mouse->input, BTN_LEFT, 0);
	input_report_key(mouse->input, BTN_RIGHT, 0);
	input_sync(mouse->input);
}

/* The lock closes the stop-versus-resubmit race. Never submit after stop. */
static int xppen_submit_locked(struct xppen_mouse *mouse)
{
	int error;

	if (!mouse->running)
		return 0;
	error = usb_submit_urb(mouse->urb, GFP_ATOMIC);
	if (error) {
		mouse->running = false;
		xppen_release(mouse);
		dev_err_ratelimited(&mouse->interface->dev,
				    "cannot submit input URB: %d\n", error);
	}
	return error;
}

static void xppen_recover(struct work_struct *work)
{
	struct xppen_mouse *mouse = container_of(work, struct xppen_mouse, recover);
	unsigned long flags;
	int error;

	/* usb_clear_halt sleeps; disconnect waits for this work before freeing. */
	error = usb_clear_halt(mouse->udev, mouse->pipe);
	spin_lock_irqsave(&mouse->lock, flags);
	if (mouse->running) {
		if (error) {
			mouse->running = false;
			xppen_release(mouse);
			dev_err(&mouse->interface->dev,
				"endpoint recovery failed: %d; run make bind\n", error);
		} else {
			xppen_submit_locked(mouse);
		}
	}
	spin_unlock_irqrestore(&mouse->lock, flags);
}

static void xppen_complete(struct urb *urb)
{
	struct xppen_mouse *mouse = urb->context;
	struct mouse_frame frame;
	unsigned long flags;

	spin_lock_irqsave(&mouse->lock, flags);
	if (!mouse->running)
		goto out;
	switch (urb->status) {
	case 0:
		if (pen_decode(&mouse->pen, mouse->buffer, urb->actual_length,
			       divisor, &frame)) {
			input_report_rel(mouse->input, REL_X, frame.dx);
			input_report_rel(mouse->input, REL_Y, frame.dy);
			input_report_key(mouse->input, BTN_LEFT, frame.left);
			input_report_key(mouse->input, BTN_RIGHT, frame.right);
			input_sync(mouse->input);
		}
		break;
	case -ENOENT:
	case -ECONNRESET:
	case -ESHUTDOWN:
		mouse->running = false;
		xppen_release(mouse);
		goto out;
	case -EPIPE:
		schedule_work(&mouse->recover);
		goto out;
	default:
		dev_warn_ratelimited(&mouse->interface->dev,
				     "input URB error: %d\n", urb->status);
		break;
	}
	xppen_submit_locked(mouse);
out:
	spin_unlock_irqrestore(&mouse->lock, flags);
}

static int xppen_start(struct xppen_mouse *mouse)
{
	unsigned long flags;
	int error;

	/* HID SET_PROTOCOL: report protocol, not the boot mouse packet format. */
	error = usb_control_msg(mouse->udev, usb_sndctrlpipe(mouse->udev, 0),
				0x0b, USB_TYPE_CLASS | USB_RECIP_INTERFACE,
				1, mouse->interface->cur_altsetting->desc.bInterfaceNumber,
				NULL, 0, USB_CTRL_SET_TIMEOUT);
	if (error < 0)
		return error;
	spin_lock_irqsave(&mouse->lock, flags);
	pen_reset(&mouse->pen);
	mouse->running = true;
	error = xppen_submit_locked(mouse);
	spin_unlock_irqrestore(&mouse->lock, flags);
	return error;
}

static void xppen_stop(struct xppen_mouse *mouse)
{
	unsigned long flags;

	spin_lock_irqsave(&mouse->lock, flags);
	mouse->running = false;
	spin_unlock_irqrestore(&mouse->lock, flags);
	usb_kill_urb(mouse->urb);
	cancel_work_sync(&mouse->recover);
	xppen_release(mouse);
}

static int xppen_probe(struct usb_interface *interface,
		       const struct usb_device_id *id)
{
	struct usb_host_interface *alt = interface->cur_altsetting;
	struct usb_endpoint_descriptor *endpoint;
	struct xppen_mouse *mouse;
	int error;

	if (divisor < 1 || divisor > 1024)
		return -EINVAL;
	if (alt->desc.bInterfaceNumber == 0) {
		dev_info(&interface->dev, "suppressing tablet's original mouse/keyboard\n");
		return 0;
	}
	if (alt->desc.bInterfaceNumber != 1)
		return -ENODEV;
	error = usb_find_int_in_endpoint(alt, &endpoint);
	if (error)
		return error;
	if (usb_endpoint_maxp(endpoint) < PEN_REPORT_SIZE || !endpoint->bInterval)
		return -ENODEV;
	mouse = kzalloc(sizeof(*mouse), GFP_KERNEL);
	if (!mouse)
		return -ENOMEM;
	mouse->udev = usb_get_dev(interface_to_usbdev(interface));
	mouse->interface = interface;
	mouse->pipe = usb_rcvintpipe(mouse->udev, endpoint->bEndpointAddress);
	mouse->buffer_size = usb_endpoint_maxp(endpoint);
	spin_lock_init(&mouse->lock);
	INIT_WORK(&mouse->recover, xppen_recover);
	mouse->urb = usb_alloc_urb(0, GFP_KERNEL);
	mouse->buffer = usb_alloc_coherent(mouse->udev, mouse->buffer_size,
					   GFP_KERNEL, &mouse->dma);
	mouse->input = input_allocate_device();
	if (!mouse->urb || !mouse->buffer || !mouse->input) {
		error = -ENOMEM;
		goto free_resources;
	}
	mouse->input->name = "XP-PEN Deco Fun L relative mouse";
	mouse->input->id.bustype = BUS_USB;
	mouse->input->id.vendor = XPPEN_VENDOR;
	mouse->input->id.product = XPPEN_PRODUCT;
	mouse->input->id.version = le16_to_cpu(mouse->udev->descriptor.bcdDevice);
	mouse->input->dev.parent = &interface->dev;
	input_set_capability(mouse->input, EV_REL, REL_X);
	input_set_capability(mouse->input, EV_REL, REL_Y);
	input_set_capability(mouse->input, EV_KEY, BTN_LEFT);
	input_set_capability(mouse->input, EV_KEY, BTN_RIGHT);
	usb_fill_int_urb(mouse->urb, mouse->udev, mouse->pipe, mouse->buffer,
			 mouse->buffer_size, xppen_complete, mouse, endpoint->bInterval);
	mouse->urb->transfer_dma = mouse->dma;
	mouse->urb->transfer_flags |= URB_NO_TRANSFER_DMA_MAP;
	error = input_register_device(mouse->input);
	if (error)
		goto free_resources;
	usb_set_intfdata(interface, mouse);
	error = xppen_start(mouse);
	if (error) {
		usb_set_intfdata(interface, NULL);
		xppen_stop(mouse);
		input_unregister_device(mouse->input);
		mouse->input = NULL;
		goto free_resources;
	}
	dev_info(&interface->dev, "relative mouse ready, divisor=%u\n", divisor);
	return 0;

free_resources:
	input_free_device(mouse->input);
	usb_free_urb(mouse->urb);
	if (mouse->buffer)
		usb_free_coherent(mouse->udev, mouse->buffer_size, mouse->buffer, mouse->dma);
	usb_put_dev(mouse->udev);
	kfree(mouse);
	return error;
}

static void xppen_disconnect(struct usb_interface *interface)
{
	struct xppen_mouse *mouse = usb_get_intfdata(interface);

	if (!mouse)
		return;
	usb_set_intfdata(interface, NULL);
	xppen_stop(mouse);
	input_unregister_device(mouse->input);
	usb_free_urb(mouse->urb);
	usb_free_coherent(mouse->udev, mouse->buffer_size, mouse->buffer, mouse->dma);
	usb_put_dev(mouse->udev);
	kfree(mouse);
}

static int xppen_suspend(struct usb_interface *interface, pm_message_t message)
{
	struct xppen_mouse *mouse = usb_get_intfdata(interface);

	if (mouse)
		xppen_stop(mouse);
	return 0;
}

static int xppen_resume(struct usb_interface *interface)
{
	struct xppen_mouse *mouse = usb_get_intfdata(interface);

	return mouse ? xppen_start(mouse) : 0;
}

static int xppen_pre_reset(struct usb_interface *interface)
{
	return xppen_suspend(interface, PMSG_SUSPEND);
}

static const struct usb_device_id xppen_ids[] = {
	{ USB_DEVICE_INTERFACE_NUMBER(XPPEN_VENDOR, XPPEN_PRODUCT, 0) },
	{ USB_DEVICE_INTERFACE_NUMBER(XPPEN_VENDOR, XPPEN_PRODUCT, 1) },
	{ }
};
MODULE_DEVICE_TABLE(usb, xppen_ids);

static struct usb_driver xppen_driver = {
	.name = "xppen_mouse",
	.id_table = xppen_ids,
	.probe = xppen_probe,
	.disconnect = xppen_disconnect,
	.suspend = xppen_suspend,
	.resume = xppen_resume,
	.reset_resume = xppen_resume,
	.pre_reset = xppen_pre_reset,
	.post_reset = xppen_resume,
};
static int __init xppen_init(void)
{
	if (divisor < 1 || divisor > 1024) {
		pr_err("xppen_mouse: divisor must be in 1..1024\n");
		return -EINVAL;
	}
	return usb_register(&xppen_driver);
}

static void __exit xppen_exit(void)
{
	usb_deregister(&xppen_driver);
}

module_init(xppen_init);
module_exit(xppen_exit);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("USB stylus-to-relative-mouse driver for XP-PEN Deco Fun L");
