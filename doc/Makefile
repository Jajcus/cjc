.PHONY: validate
.SUFFIXES: .xml .fo .dvi .ps .pdf .html

all: manual.html

.fo.pdf:
	pdfxmltex $<

.fo.dvi:
	xmltex $<

.dvi.ps:
	dvips -o $@ $<

#.xml.html:
#	xsltproc -o $@ /usr/share/sgml/docbook/xsl-stylesheets/html/docbook.xsl $<

.xml.html:
	xsltproc -o $@ /usr/share/sgml/docbook/xsl-stylesheets/xhtml/docbook.xsl $<

.xml.fo:
	xsltproc -o $@ /usr/share/sgml/docbook/xsl-stylesheets/fo/docbook.xsl $<

validate:
	xmllint --valid --noout *.xml
