#!/bin/bash

cd rpz && pdflatex ./report.tex && pdflatex ./report.tex && pdflatex ./report.tex
gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dNOPAUSE -dOptimize=true -dQUIET -dBATCH -dRemoveUnusedFonts=true -dRemoveUnusedImages=true -dOptimizeResources=true -dDetectDuplicateImages -dCompressFonts=true -dEmbedAllFonts=true -dSubsetFonts=true -dPreserveAnnots=true -dPreserveMarkedContent=true -dPreserveOverprintSettings=true -dPreserveHalftoneInfo=true -dPreserveOPIComments=true -dPreserveDeviceN=true -dMaxInlineImageSize=0 -sOutputFile=../ready/report.pdf ./report.pdf
rm ./report.pdf
cd .. || exit
cp ./ready/report.pdf ./rpz/report.pdf
