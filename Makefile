
prefix=/usr/local
bindir=$(prefix)/bin
datadir=$(prefix)/share
docdir=$(datadir)/doc

DESTDIR=

INSTALL=install
INSTALL_DATA=install -m 644
INSTALL_DIR=install -d

UNINSTALL=rm
UNINSTALL_DIR=rm -r

pkg_datadir=$(datadir)/cjc
pkg_docdir=$(docdir)/cjc

BASE_VERSION=0.1

PY_DIRS=cjc cjc/ui plugins
DOCS=doc/manual.html COPYING ChangeLog

EXTRA_DIST=Makefile cjc.in cjc.py

.PHONY: all cvs-version dist

all: cjc.inst cjc/version.py $(DOCS) 

doc/manual.html: doc/manual.xml 
	cd doc; make

cjc/version.py: cvs-version

cvs-version:
	SNAPSHOT=.`find . -name "*.py" '!' -name "version.py" -printf '%TY%Tm%Td/%TH:%TM\n' | sort -r | head -1` ; \
	echo "version='$(BASE_VERSION)$$SNAPSHOT'" > cjc/version.py ;

version:
	echo "version='$(BASE_VERSION)'" > cjc/version.py 

cjc.inst: cjc.in
	sed -e 's,BASE_DIR,$(pkg_datadir),' < cjc.in > cjc.inst 

install: all
	for d in $(PY_DIRS) ; do \
		$(INSTALL_DIR) $(DESTDIR)$(pkg_datadir)/$$d ; \
		$(INSTALL_DATA) $$d/*.py $(DESTDIR)$(pkg_datadir)/$$d ; \
	done
	$(INSTALL_DIR) $(DESTDIR)$(pkg_docdir)
	$(INSTALL_DATA) $(DOCS) $(DESTDIR)$(pkg_docdir)
	$(INSTALL_DIR) $(DESTDIR)$(bindir)
	$(INSTALL) cjc.inst $(DESTDIR)$(bindir)/cjc

uninstall:
	for d in $(PY_DIRS) ; do \
		$(UNINSTALL_DIR) $(DESTDIR)$(pkg_datadir)/$$d ; \
	done || :
	$(UNINSTALL_DIR) $(DESTDIR)$(pkg_datadir) || :
	$(UNINSTALL_DIR) $(DESTDIR)$(pkg_docdir) || :
	$(UNINSTALL) $(DESTDIR)$(bindir)/cjc || :
