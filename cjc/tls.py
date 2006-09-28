# Console Jabber Client
# Copyright (C) 2004-2006  Jacek Konieczny
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

from cjc import common
from cjc import cjc_globals

SUBJECT_NAME_INVALID = 1000

try:
    from M2Crypto import m2

    tls_errors = {
        m2.X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT: "unable to get issuer certificate",
        m2.X509_V_ERR_UNABLE_TO_GET_CRL: "unable to get certificate CRL",
        m2.X509_V_ERR_UNABLE_TO_DECRYPT_CERT_SIGNATURE: "unable to decrypt certificate's signature",
        m2.X509_V_ERR_UNABLE_TO_DECRYPT_CRL_SIGNATURE: "unable to decrypt CRL's signature",
        m2.X509_V_ERR_UNABLE_TO_DECODE_ISSUER_PUBLIC_KEY: "unable to decode issuer public key",
        m2.X509_V_ERR_CERT_SIGNATURE_FAILURE: "certificate signature failure",
        m2.X509_V_ERR_CRL_SIGNATURE_FAILURE: "CRL signature failure",
        m2.X509_V_ERR_CERT_NOT_YET_VALID: "certificate is not yet valid",
        m2.X509_V_ERR_CERT_HAS_EXPIRED: "certificate has expired",
        m2.X509_V_ERR_CRL_NOT_YET_VALID: "CRL is not yet valid",
        m2.X509_V_ERR_CRL_HAS_EXPIRED: "CRL has expired",
        m2.X509_V_ERR_ERROR_IN_CERT_NOT_BEFORE_FIELD: "format error in certificate's notBefore field",
        m2.X509_V_ERR_ERROR_IN_CERT_NOT_AFTER_FIELD: "format error in certificate's notAfter field",
        m2.X509_V_ERR_ERROR_IN_CRL_LAST_UPDATE_FIELD: "format error in CRL's lastUpdate field",
        m2.X509_V_ERR_ERROR_IN_CRL_NEXT_UPDATE_FIELD: "format error in CRL's nextUpdate field",
        m2.X509_V_ERR_OUT_OF_MEM: "out of memory",
        m2.X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT: "self signed certificate",
        m2.X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN: "self signed certificate in certificate chain",
        m2.X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT_LOCALLY: "unable to get local issuer certificate",
        m2.X509_V_ERR_UNABLE_TO_VERIFY_LEAF_SIGNATURE: "unable to verify the first certificate",
        m2.X509_V_ERR_CERT_CHAIN_TOO_LONG: "certificate chain too long",
        m2.X509_V_ERR_CERT_REVOKED: "certificate revoked",
        m2.X509_V_ERR_INVALID_CA: "invalid CA certificate",
        m2.X509_V_ERR_PATH_LENGTH_EXCEEDED: "path length constraint exceeded",
        m2.X509_V_ERR_INVALID_PURPOSE: "unsupported certificate purpose",
        m2.X509_V_ERR_CERT_UNTRUSTED: "certificate not trusted",
        m2.X509_V_ERR_CERT_REJECTED: "certificate rejected",

        # # taken from `man openssl_verify`
        29: "subject issuer mismatch",
        30: "authority and subject key identifier mismatch",
        31: "authority and issuer serial number mismatch",
        32: "key usage does not include certificate signing",

        m2.X509_V_ERR_APPLICATION_VERIFICATION: "application verification failure",

        # internal CJC error code
        SUBJECT_NAME_INVALID: "Certificate subject name doesn't match peer's JID"
    }

    # these will be ignored if the certificate is known as trustworthy
    tls_nonfatal_errors = {
        m2.X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT: True, 
        m2.X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT: True, 
        m2.X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN: True, 
        m2.X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT_LOCALLY: True, 
        m2.X509_V_ERR_UNABLE_TO_VERIFY_LEAF_SIGNATURE: True, 
        m2.X509_V_ERR_CERT_CHAIN_TOO_LONG: True, 
        m2.X509_V_ERR_INVALID_CA: True, 
        m2.X509_V_ERR_PATH_LENGTH_EXCEEDED: True, 
        m2.X509_V_ERR_INVALID_PURPOSE: True, 
        m2.X509_V_ERR_CERT_UNTRUSTED: True, 
        m2.X509_V_ERR_CERT_REJECTED: True, 

        32: True,

        SUBJECT_NAME_INVALID: True,
    }
except ImportError:
    pass

class Struct:
    def __init__(self):
        pass

class CertVerifyState:
    def __init__(self):
        self.certs = {}
        self.errors = {}
        self.has_fatal_errors = False
        self.tls_known_cert = None
        self.known_root_cacert = None
        
    def add_error(self,depth,errnum):
        if errnum not in tls_nonfatal_errors:
            self.has_fatal_errors = True
        if self.errors.has_key(depth):
            self.errors[depth].append(errnum)
        else:
            self.errors[depth] = [errnum]
            
    def has_errors(self):
        if self.errors:
            return 1
        else:
            return 0
            
    def get_errors(self,depth):
        return self.errors.get(depth, [])
        
    def set_cert(self,depth,cert):
        self.certs[depth] = cert
        
    def get_max_dept(self):
        return max(self.certs.keys())

    def get_cert(self,depth):
        return self.certs[depth]

class TLSMixIn:
    """ Mix-in class with utility classes for TLS support in the Client. """
    def __init__(self):
        self.__logger=logging.getLogger("cjc.Application")

    def tls_init(self):
        if self.settings.get("tls_enable"):
            self.tls_settings=pyxmpp.TLSSettings(
                    require=self.settings.get("tls_require"),
                    cert_file=self.settings.get("tls_cert_file"),
                    key_file=self.settings.get("tls_key_file"),
                    cacert_file=self.settings.get("tls_ca_cert_file"),
                    verify_callback=self.cert_verification_callback
                    )

            if self.server:
                self.tls_peer_name=self.server
            else:
                self.tls_peer_name=self.jid.domain
            if self.port and self.port!=5222:
                self.tls_peer_name="%s:%i" % (self.tls_peer_name,self.port)

            self.cert_verify_state=CertVerifyState()
            self.tls_known_cert=None
        else:
            self.tls_settings=None
            self.cert_verify_state=None

    def tls_connected(self,tls):
        cipher=tls.get_cipher()
        self.__logger.info("Encrypted connection to %s established using cipher %s.",
                            unicode(self.stream.peer), cipher.name())
        if not self.cert_verify_state.has_errors():
            return
        cert=self.cert_verify_state.get_cert(0)
        if self.tls_is_cert_known(cert):
            return
        if self.cert_verify_state.has_fatal_errors:
            return
        self.cert_remember_ask(cert)

    def cert_remember_ask(self,cert):
        buf=ui.TextBuffer({})
        p={
            "who": self.tls_peer_name,
            "subject": cert.get_subject(),
            "issuer": cert.get_issuer(),
            "serial_number": cert.get_serial_number(),
            "not_before": cert.get_not_before(),
            "not_after": cert.get_not_after(),
            "certificate": "certificate",
            }
        buf.append_themed("certificate_remember",p)
        arg=Struct()
        arg.cert=cert
        arg.name=self.tls_peer_name
        arg.buf=buf
        arg.verify_state=self.cert_verify_state
        def callback(response):
            return self.cert_remember_decision(response, arg)
        buf.ask_question("Always accept?",
            "boolean",None,callback,None,None,1)
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
        f.write(arg.cert.as_der())
        f.close()
        logger.info("Peer certificate saved to: "+p)

    def cert_verification_callback(self, ok, store_context):
        logger = logging.getLogger("cjc.TLSHandler")
        try:
            depth = store_context.get_error_depth()
            cert = store_context.get_current_cert()
            errnum = store_context.get_error()
            cn = cert.get_subject().CN

            logger.debug("cert_verification_callback(depth=%i, ok=%i)" % (depth, ok))
            self.cert_verify_state.set_cert(depth, cert)
            if not ok:
                self.cert_verify_state.add_error(depth, errnum)
                
            if depth == 0 and not self.stream.tls_is_certificate_valid(store_context):
                subject_name_valid = False
                self.cert_verify_state.add_error(depth, SUBJECT_NAME_INVALID)
            else:
                subject_name_valid = True

            pcert = self.stream.tls.get_peer_cert()
            if depth == 0 and self.tls_is_cert_known(cert):
                if not ok and tls_nonfatal_errors.get(errnum):
                    errdesc = tls_errors.get(errnum, "unknown")
                    self.status_buf.append_themed("tls_error_ignored",
                            {"errnum": errnum, "errdesc": errdesc})
                    return 1
                if not subject_name_valid:
                    self.status_buf.append_themed("tls_error_ignored",
                            {"errnum": SUBJECT_NAME_INVALID, "errdesc": tls_errors[SUBJECT_NAME_INVALID]})
                    return ok
                if not ok:
                    errdesc = tls_errors.get(errnum, "unknown")
                    self.status_buf.append_themed("tls_error_not_ignored",
                            {"errnum": errnum, "errdesc": errdesc})
            
            logger.debug("ok=%r subject_name_valid=%r" % (ok, subject_name_valid))
            if not ok:
                return self.cert_verify_ask(cert, errnum, depth)
            elif not subject_name_valid:
                return self.cert_verify_ask(cert, SUBJECT_NAME_INVALID, depth)
            else:
                return True
        except:
            self.__logger.exception("Exception during certificate verification:")
            raise

    def tls_is_cert_known(self,cert):
        from M2Crypto import X509
        logger=logging.getLogger("cjc.TLSHandler")
        if not self.tls_known_cert:
            p=os.path.join(self.home_dir,"known_certs",self.tls_peer_name+".der")
            logger.debug("Loading cert file: "+p)
            try:
                self.tls_known_cert=file(p,"r").read()
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
        elif self.tls_known_cert==cert.as_der():
            logger.debug("the same cert known")
            return 1
        else:
            logger.debug("other cert known")
            logger.debug("known: "+`self.tls_known_cert`)
            logger.debug("new:"+`cert.as_der()`)
            return 0

    def cert_verify_ask(self, cert, errnum, depth):
        buf=ui.TextBuffer({})
        errdesc=tls_errors.get(errnum,"unknown")
        p={
            "depth": depth,
            "errnum": errnum,
            "errdesc": errdesc,
            "subject": cert.get_subject(),
            "issuer": cert.get_issuer(),
            "serial_number": cert.get_serial_number(),
            "not_before": cert.get_not_before(),
            "not_after": cert.get_not_after(),
            "certificate": "certificate",
            "chain": self.format_cert_chain,
            "chain_data": self.stream.tls.get_peer_cert_chain(),
            }
        buf.append_themed("certificate_error",p)
        arg=Struct()
        arg.ok=None
        cond=threading.Condition()
        def callback(response):
            cond.acquire()
            arg.ok=response
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

    def format_cert_chain(self,attr,params):
        logger=logging.getLogger("cjc.TLSHandler")
        logger.debug("format_cert_chain(%r,%r,%r)" % (self,attr,params))
        chain=params.get("chain_data")
        if not chain:
            return cjc_globals.theme_manager.do_format_string("  <none>\n",attr,params)
        f = cjc_globals.theme_manager.formats["certificate"]
        ret=[]
        for cert in chain:
            p={
                "subject": cert.get_subject(),
                "issuer": cert.get_issuer(),
                "serial_number": cert.get_serial_number(),
                "not_before": cert.get_not_before(),
                "not_after": cert.get_not_after(),
                }
            ret+=cjc_globals.theme_manager.do_format_string(f,attr,p)
        return ret

# vi: sts=4 et sw=4
