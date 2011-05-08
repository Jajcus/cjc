# Console Jabber Client
# Copyright (C) 2004-2010  Jacek Konieczny
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published
# by the Free Software Foundation
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

import pyxmpp
import ui
import threading
import os
import logging
import subprocess

from collections import namedtuple

from cjc import common
from cjc import cjc_globals

CACERT_FILE_LOCATIONS = [
        '/etc/certs/ca-certificates.crt', # e.g. PLD Th
        '/etc/ssl/certs/ca-certificates.crt', # e.g. Debian
        '/etc/pki/tls/certs/ca-bundle.crt', # Fedora
        '/etc/openssl/ca-certificates.crt', # old PLD
        '/usr/share/ssl/ca-bundle.crt', # old PLD
        '/usr/share/ssl/certs/ca-bundle.crt', # ?
        '/etc/ssl/certs/ca-bundle.crt', # ?
        ]

class Struct:
    pass

class TLSMixIn:
    """ Mix-in class with utility classes for TLS support in the Client. """
    def __init__(self):
        self.__logger=logging.getLogger("cjc.Application")

    def tls_init(self):
        if self.settings.get("tls_enable"):
            cacert_file = self.settings.get("tls_ca_cert_file")
            if not cacert_file:
                for location in CACERT_FILE_LOCATIONS:
                    if os.path.exists(location):
                        cacert_file = location
                        break
                if cacert_file:
                    self.__logger.info("tls_ca_cert_file not set, using {0}"
                                                            .format(cacert_file))
                else:
                    self.__logger.warning("tls_ca_cert_file not set"
                            " and system CA certificate list not found."
                            " Expect failure.")
            else:
                cacert_file = os.path.expanduser(cacert_file)
            self.tls_settings = pyxmpp.TLSSettings(
                    require = self.settings.get("tls_require"),
                    cert_file = self.settings.get("tls_cert_file"),
                    key_file = self.settings.get("tls_key_file"),
                    cacert_file = cacert_file,
                    verify_peer = self.settings.get("tls_verify", True),
                    verify_callback = self.cert_verification_callback
                    )

            if self.server:
                self.tls_peer_name=self.server
            else:
                self.tls_peer_name=self.jid.domain
            if self.port and self.port!=5222:
                self.tls_peer_name="%s:%i" % (self.tls_peer_name,self.port)

        self.cert_verify_error = None
        self.tls_known_cert = None

    def tls_connected(self, tls):
        cipher, ssl_version, bits = tls.cipher()
        self.__logger.info(u"Encrypted connection to {0} established using" 
                    " {1}, {2} ({3} bits)".format(unicode(self.stream.peer),
                                                    ssl_version, cipher, bits))
        verified = self.settings.get("tls_verify", True)
        if verified and not self.cert_verify_error:
            return
        cert = tls.getpeercert()
        der_cert = tls.getpeercert(binary_form = True)
        if self.tls_is_cert_known(der_cert):
            if not verified:
                self.__logger.warning("Server certificate not verified,"
                                    " but accepted as already known.")
            return
        if not verified:
            cert = self._decode_der_cert(der_cert)
            ok = self.cert_verify_ask(cert,
                                        "Certificate not verified")
            if not ok:
                self.disconnect()
                return
        self.cert_remember_ask(cert, der_cert)
    
    @staticmethod
    def _decode_der_cert(der_cert):
        """Decode binary certifiacte with 'opessl x509' command."""
        pipe = subprocess.Popen(["openssl", "x509", "-inform", "DER", "-noout",
                                    "-issuer", "-subject", "-serial", "-dates"],
                            stdin = subprocess.PIPE, stdout = subprocess. PIPE)
        pipe.stdin.write(der_cert)
        pipe.stdin.close()
        result = {}
        for line in pipe.stdout:
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key in ('serial', 'notBefore', 'notAfter'):
                result[key] = value.strip()
            elif key in ('issuer', 'subject'):
                result[key + "_string"] = value.strip()
        pipe.stdout.close()
        rc = pipe.wait()
        if rc:
            self.__logger.debug("openssl x509 exited with {0}".format(rc))
            return {}
        return result

    @staticmethod
    def _cert_dn(cert, field):
        if field + "_string" in cert:
            return cert[field + "_string"]
        if field not in cert:
            return None
        return ", ".join([
            ", ".join([u"{0}={1}".format(key, value) for key, value in rdn])
                for rdn in cert[field]])

    @staticmethod
    def _cert_subject_alt_name(cert):
        if "subjectAltName" not in cert:
            return None
        return ", ".join([u"{0}: {1}".format(key, value)
                                for key, value in cert["subjectAltName"]])

    def cert_remember_ask(self, cert, der_cert):
        buf = ui.TextBuffer({})
        p = {
            "who": self.tls_peer_name,
            "subject": self._cert_dn(cert, "subject"),
            "subject_alt_name": self._cert_subject_alt_name(cert),
            "issuer": self._cert_dn(cert, "issuer"),
            "serial_number": cert.get("serial"),
            "not_before": cert.get('notBefore'),
            "not_after": cert.get('notAfter'),
            "certificate": "certificate",
            }
        buf.append_themed("certificate_remember", p)
        arg = Struct()
        arg.cert = cert
        arg.der_cert = der_cert
        arg.name = self.tls_peer_name
        arg.buf = buf
        def callback(response):
            return self.cert_remember_decision(response, arg)
        buf.ask_question("Always accept?", "boolean", None, callback,
                                                                None, None, 1)
        buf.update()

    def cert_remember_decision(self, ans, arg):
        logger=logging.getLogger("cjc.TLSHandler")
        arg.buf.close()
        if not ans:
            return
        d=os.path.join(self.home_dir,"known_certs")
        if not os.path.exists(d):
            os.makedirs(d)
        p=os.path.join(d,self.tls_peer_name+".der")
        f=file(p,"w")
        f.write(arg.der_cert)
        f.close()
        logger.info("Peer certificate saved to: "+p)

    def cert_verification_callback(self, cert):
        logger = logging.getLogger("cjc.TLSHandler")
        try:
            if not self.stream.tls_is_certificate_valid(cert):
                subject_name_valid = False
                self.cert_verify_error = "Hostname mismatch"
            else:
                subject_name_valid = True

            der_cert = self.stream.tls.getpeercert(binary_form = True)
            if self.tls_is_cert_known(der_cert):
                if not subject_name_valid:
                    self.status_buf.append_themed("tls_error_ignored",
                            {"errdesc": "Certificate subject name doesn't"
                                                        " match server name"})
                    return True
            
            logger.debug("subject_name_valid=%r" % (subject_name_valid,))
            if not subject_name_valid:
                return self.cert_verify_ask(cert, "Certificate doesn't match peer name.")
            else:
                return True
        except:
            self.__logger.exception("Exception during certificate verification:")
            raise

    def tls_is_cert_known(self, der_cert):
        logger = logging.getLogger("cjc.TLSHandler")
        if not self.tls_known_cert:
            p = os.path.join(self.home_dir, "known_certs", self.tls_peer_name + ".der")
            logger.debug("Loading cert file: " + p)
            try:
                self.tls_known_cert = file(p, "r").read()
                logger.info("Last known peer certificate loaded from: "+p)
            except IOError,e:
                logger.debug("Exception: "+str(e))
                self.tls_known_cert="unknown"
            except:
                self.tls_known_cert="unknown"
                raise
            logger.debug("cert loaded: "+`self.tls_known_cert`)
        if self.tls_known_cert=="unknown":
            logger.debug("cert unknown")
            return 0
        elif self.tls_known_cert == der_cert:
            logger.debug("the same cert known")
            return 1
        else:
            logger.debug("other cert known")
            logger.debug("known: " + `self.tls_known_cert`)
            logger.debug("new:" + `der_cert`)
            return 0

    def cert_verify_ask(self, cert, errdesc):
        buf=ui.TextBuffer({})
        p={
            "depth": 0,
            "errdesc": errdesc,
            "subject": self._cert_dn(cert, "subject"),
            "subject_alt_name": self._cert_subject_alt_name(cert),
            "issuer": self._cert_dn(cert, "issuer"),
            "serial_number": cert.get("serial"),
            "not_before": cert.get("notBefore"),
            "not_after": cert.get("notAfter"),
            "certificate": "certificate",
            "chain": "unknown",
            "chain_data": "unknown",
            }
        buf.append_themed("certificate_error", p)
        arg = Struct()
        arg.ok = None
        cond = threading.Condition()
        def callback(response):
            cond.acquire()
            arg.ok = response
            cond.notify()
            cond.release()
        buf.ask_question("Accept?", "boolean", None, callback, None, None, 1)
        cjc_globals.screen.display_buffer(buf)
        cond.acquire()
        while arg.ok is None:
            cond.wait()
        cond.release()
        buf.close()
        return arg.ok

# vi: sts=4 et sw=4
