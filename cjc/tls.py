import pyxmpp
import ui
import threading
import os
import common


tls_errors={ # taken from `man openssl_verify`
	0: "ok",
	2: "unable to get issuer certificate",
	3: "unable to get certificate CRL",
	4: "unable to decrypt certificate's signature",
	5: "unable to decrypt CRL's signature",
	6: "unable to decode issuer public key",
	7: "certificate signature failure",
	8: "CRL signature failure",
	9: "certificate is not yet valid",
	10: "certificate has expired",
	11: "CRL is not yet valid",
	12: "CRL has expired",
	13: "format error in certificate's notBefore field",
	14: "format error in certificate's notAfter field",
	15: "format error in CRL's lastUpdate field",
	16: "format error in CRL's nextUpdate field",
	17: "out of memory",
	18: "self signed certificate",
	19: "self signed certificate in certificate chain",
	20: "unable to get local issuer certificate",
	21: "unable to verify the first certificate",
	22: "certificate chain too long",
	23: "certificate revoked",
	24: "invalid CA certificate",
	25: "path length constraint exceeded",
	26: "unsupported certificate purpose",
	27: "certificate not trusted",
	28: "certificate rejected",
	29: "subject issuer mismatch",
	30: "authority and subject key identifier mismatch",
	31: "authority and issuer serial number mismatch",
	32: "key usage does not include certificate signing",
	50: "application verification failure",

	# PyXMPP errors below
	1001: "certificate CN doesn't match server name",
}

class Struct:
	def __init__(self):
		pass

class CertVerifyState:
	def __init__(self):
		self.certs={}
		self.errors={}
		self.tls_known_cert=None
		self.known_root_cacert=None
	def add_error(self,depth,errnum):
		if self.errors.has_key(depth):
			self.errors[depth].append(errnum)
		else:
			self.errors[depth]=[errnum]
	def has_errors(self):
		if self.errors:
			return 1
		else:
			return 0
	def get_errors(self,depth):
		return self.errors.get(depth,[])
	def set_cert(self,depth,cert):
		self.certs[depth]=cert
	def get_max_dept(self):
		return max(self.certs.keys())
	def get_cert(self,depth):
		return self.certs[depth]

class TLSHandler:
	""" Add-on class with utility classes for TLS support in the Client. """
	def __init__(self):
		raise "This is virtual class"
	
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
		self.info("Encrypted connection to %s established using cipher %s."
							% (self.stream.peer,cipher.name()))
		if not self.cert_verify_state.has_errors():
			return
		cert=self.cert_verify_state.get_cert(0)
		if self.tls_is_cert_known(cert):
			return
		self.cert_remember_ask(cert)

	def cert_remember_ask(self,cert):
		buf=ui.TextBuffer(self.theme_manager,{})
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
		buf.ask_question("Always accept?",
			"boolean",None,self.cert_remember_decision,None,arg,None,1)
		buf.update()

	def cert_remember_decision(self,arg,ans):
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
		self.info("Peer certificate saved to: "+p)

	def cert_verification_callback(self,stream,ctx,cert,errnum,depth,ok):
		self.debug("cert_verification_callback(depth=%i,ok=%i)" % (depth,ok))
		try:
			self.cert_verify_state.set_cert(depth,cert)
			if not ok:
				self.cert_verify_state.add_error(depth,errnum)
			pcert=self.stream.tls.get_peer_cert()
			if depth==0 and self.tls_is_cert_known(cert):
				if not ok:
					errdesc=tls_errors.get(errnum,"unknown")
					self.status_buf.append_themed("tls_error_ignored",
							{"errnum": errnum, "errdesc": errdesc})
				return 1
			return self.cert_verify_ask(ctx,cert,errnum,depth)
		except:
			self.print_exception()
			raise
	
	def tls_is_cert_known(self,cert):
		from M2Crypto import X509
		if not self.tls_known_cert:
			p=os.path.join(self.home_dir,"known_certs",self.tls_peer_name+".der")
			common.debug("Loading cert file: "+p)
			try:
				self.tls_known_cert=file(p,"r").read()
				self.info("Last known peer certificate loaded from: "+p)
			except IOError,e:
				common.debug("Exception: "+str(e))
				self.tls_known_cert="unknown"
			except:
				self.tls_known_cert="unknown"
				raise
			common.debug("cert loaded: "+`self.tls_known_cert`)
		if self.tls_known_cert=="unknown":
			common.debug("cert unknown")
			return 0
		elif self.tls_known_cert==cert.as_der():
			common.debug("the same cert known")
			return 1
		else:
			common.debug("other cert known")
			common.debug("known: "+`self.tls_known_cert`)
			common.debug("new:"+`cert.as_der()`)
			return 0

	def cert_verify_ask(self,ctx,cert,errnum,depth):
		buf=ui.TextBuffer(self.theme_manager,{})
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
		arg.cond=threading.Condition()
		buf.ask_question("Accept?","boolean",None,self.cert_verify_decision,None,arg,None,1)
		self.screen.display_buffer(buf)
		arg.cond.acquire()
		while arg.ok is None:
			arg.cond.wait()
		arg.cond.release()
		buf.close()
		return arg.ok

	def cert_verify_decision(self,arg,ans):
		arg.cond.acquire()
		arg.ok=ans
		arg.cond.notify()
		arg.cond.release()

	def format_cert_chain(self,attr,params):
		self.debug("format_cert_chain(%r,%r,%r)" % (self,attr,params))
		chain=params.get("chain_data")
		if not chain:
			return self.theme_manager.do_format_string("  <none>\n",attr,params)
		f=self.theme_manager.formats["certificate"]
		ret=[]
		for cert in chain:
			p={
				"subject": cert.get_subject(),
				"issuer": cert.get_issuer(),
				"serial_number": cert.get_serial_number(),
				"not_before": cert.get_not_before(),
				"not_after": cert.get_not_after(),
				}
			ret+=self.theme_manager.do_format_string(f,attr,p)
		return ret

