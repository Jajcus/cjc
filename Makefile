
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

BASE_VERSION=0.2
RELEASE=

PY_DIRS=cjc cjc/ui plugins
DOCS=doc/manual.html COPYING ChangeLog README TODO

EXTRA_DIST=Makefile cjc.in cjc.py doc/manual.xml doc/Makefile

.PHONY: all version dist

all: cjc.inst $(DOCS) version

doc/manual.html: doc/manual.xml 
	cd doc; make

version:
	if test -n "$(RELEASE)" ; then \
		SNAPSHOT="" ; \
	else \
		SNAPSHOT=.`find . -name "*.py" '!' -name "version.py" -printf '%TY%Tm%Td_%TH%TM\n' | sort -r | head -1` ; \
	fi ; \
	echo "version='$(BASE_VERSION)$$SNAPSHOT'" > cjc/version.py ;

cjc.inst: cjc.in
	sed -e 's,BASE_DIR,$(pkg_datadir),' < cjc.in > cjc.inst 

clean:
	-rm -f cjc.inst

install: all
	for d in $(PY_DIRS) ; do \
		$(INSTALL_DIR) $(DESTDIR)$(pkg_datadir)/$$d ; \
		$(INSTALL_DATA) $$d/*.py $(DESTDIR)$(pkg_datadir)/$$d ; \
	done
	python -c "import compileall; compileall.compile_dir('$(DESTDIR)$(pkg_datadir)')" 
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

dist: all
	version=`python -c "import cjc.version; print cjc.version.version"` ; \
	distname=cjc-$$version ; \
	for d in $(PY_DIRS) ; do \
		$(INSTALL_DIR) $$distname/$$d || exit 1 ; \
		cp -a $$d/*.py $$distname/$$d || exit 1 ; \
	done || exit 1 ; \
	for f in $(DOCS) $(EXTRA_DIST) ; do \
		d=`dirname $$f` ; \
		$(INSTALL_DIR) $$distname/$$d || exit 1; \
		cp -a $$f $$distname/$$d || exit 1; \
	done ; \
	tar czf $${distname}.tar.gz $$distname && \
	rm -r $$distname
