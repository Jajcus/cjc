.PHONY: validate
.SUFFIXES: .xml .fo .dvi .ps .pdf .html

XSLTPROC=/usr/bin/xsltproc
XSL_DIR=/usr/share/sgml/docbook/xsl-stylesheets/
HTML_STYLESHEET=$(XSL_DIR)/xhtml/docbook.xsl
FO_STYLESHEET=$(XSL_DIR)/xhtml/docbook.xsl

all: 
	[ "x$(XSLTPROC)" != "x" ] \
		&& [ -x "$(XSLTPROC)" ] \
		&& [ -f "$(HTML_STYLESHEET)" ] \
		&& make manual.html || :

.fo.pdf:
	pdfxmltex $<

.fo.dvi:
	xmltex $<

.dvi.ps:
	dvips -o $@ $<

.xml.html:
	xsltproc -o $@ $(HTML_STYLESHEET) $<

.xml.fo:
	xsltproc -o $@ $(FO_STYLESHEET) $<

validate:
	xmllint --valid --noout *.xml
