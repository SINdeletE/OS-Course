ifneq ($(KERNELRELEASE),)
obj-m := xppen_mouse.o
xppen_mouse-y := src/main.o
else
KDIR ?= /lib/modules/$(shell uname -r)/build
DIVISOR ?= 8
PYTHON ?= python3
.DEFAULT_GOAL := all
.PHONY: all load bind unload clean

all:
	@test -d "$(KDIR)" || { echo "Kernel headers missing: $(KDIR)" >&2; exit 1; }
	$(MAKE) -C "$(KDIR)" M="$(CURDIR)" W=1 modules

# Run these three targets as root inside Ubuntu: sudo make load/bind/unload.
load: all
	$(PYTHON) scripts/manage.py load --module "$(CURDIR)/xppen_mouse.ko" --divisor "$(DIVISOR)"

bind:
	$(PYTHON) scripts/manage.py bind

unload:
	$(PYTHON) scripts/manage.py unload

clean:
	$(PYTHON) scripts/clean.py
endif
