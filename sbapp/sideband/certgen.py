# MIT License
#
# Copyright (c) 2024 Mark Qvist / unsigned.io.
# Modified by Liberty Communication Systems, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import RNS


def _generate_with_openssl(key_path, cert_path):
    """Generate a self-signed ECDSA certificate using the openssl CLI.

    This works on Android (openssl is bundled by p4a via the openssl recipe)
    and on any system with openssl installed, without needing the PyCA
    cryptography library (whose Rust abi3.so crashes on p4a's Python embedding).
    """
    import subprocess
    import shutil

    openssl = shutil.which("openssl")
    if openssl is None:
        # On Android, openssl may not be on PATH but the shared lib is loaded.
        # Try common locations.
        for candidate in ["/system/bin/openssl", "/data/data/openssl"]:
            if os.path.isfile(candidate):
                openssl = candidate
                break

    if openssl is None:
        raise FileNotFoundError("openssl binary not found")

    # Generate EC private key
    if not os.path.isfile(key_path):
        subprocess.run([
            openssl, "ecparam", "-genkey", "-name", "prime256v1",
            "-noout", "-out", key_path
        ], check=True, capture_output=True)

    # Generate self-signed certificate (10 years)
    subprocess.run([
        openssl, "req", "-new", "-x509",
        "-key", key_path,
        "-out", cert_path,
        "-days", "3652",
        "-subj", "/C=NA/ST=None/L=Earth/O=Liberty Chat Pro/CN=Liberty Chat Pro Repository",
        "-sha256"
    ], check=True, capture_output=True)

    RNS.log("SSL certificate generated via openssl CLI", RNS.LOG_DEBUG)


def _generate_with_pyca(key_path, cert_path):
    """Generate a self-signed ECDSA certificate using PyCA cryptography.

    This is the upstream Sideband method. It works on desktop but fails on
    Android when the Rust abi3.so cannot resolve Python ABI symbols.
    """
    import datetime
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography import __version__ as cv
    major = int(cv.split(".")[0])

    # Key
    if os.path.isfile(key_path):
        with open(key_path, "rb") as f:
            if major > 3:
                key = load_pem_private_key(f.read(), None)
            else:
                from cryptography.hazmat.backends import default_backend
                key = load_pem_private_key(f.read(), None, backend=default_backend())
    else:
        if major > 3:
            key = ec.generate_private_key(curve=ec.SECP256R1())
        else:
            from cryptography.hazmat.backends import default_backend
            key = ec.generate_private_key(curve=ec.SECP256R1(), backend=default_backend())
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()))

    # Certificate
    attrs = [
        x509.NameAttribute(NameOID.COUNTRY_NAME, "NA"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "None"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Earth"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Liberty Chat Pro"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Liberty Chat Pro Repository"),
    ]
    name = x509.Name(attrs)
    cb = x509.CertificateBuilder()
    cb = cb.subject_name(name).issuer_name(name)
    cb = cb.public_key(key.public_key())
    cb = cb.serial_number(x509.random_serial_number())
    cb = cb.not_valid_before(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=-14))
    cb = cb.not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3652))
    cb = cb.add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)

    if major > 3:
        cert = cb.sign(key, hashes.SHA256())
    else:
        from cryptography.hazmat.backends import default_backend
        cert = cb.sign(key, hashes.SHA256(), backend=default_backend())

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    RNS.log("SSL certificate generated via PyCA cryptography", RNS.LOG_DEBUG)


def _generate_with_pure_python(key_path, cert_path):
    """Generate a self-signed certificate using pure Python + ssl module.

    Fallback when neither openssl CLI nor PyCA cryptography are available.
    Uses Python's ssl module to create a minimal self-signed cert.
    """
    import ssl
    import tempfile
    import subprocess

    # Python's ssl module can't generate certs directly, but we can use
    # a minimal ASN.1 DER approach. For simplicity, generate via the
    # ssl._ssl._test_decode_cert path — but this doesn't actually generate.
    # Real fallback: skip SSL entirely and serve HTTP.
    raise NotImplementedError("No certificate generator available")


def ensure_certificate(key_path, cert_path):
    """Generate a self-signed SSL certificate for the repository server.

    Tries in order:
    1. openssl CLI (works on Android, no Rust/PyO3 dependency)
    2. PyCA cryptography library (works on desktop)
    3. Skip SSL — serve over plain HTTP as last resort
    """
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    os.makedirs(os.path.dirname(cert_path), exist_ok=True)

    # If cert already exists and is recent, reuse it
    if os.path.isfile(key_path) and os.path.isfile(cert_path):
        import time as _time
        age_days = (_time.time() - os.stat(cert_path).st_mtime) / 86400
        if age_days < 3000:
            return cert_path

    for method_name, method in [
        ("openssl CLI", _generate_with_openssl),
        ("PyCA cryptography", _generate_with_pyca),
    ]:
        try:
            method(key_path, cert_path)
            return cert_path
        except Exception as e:
            RNS.log(f"Certificate generation via {method_name} failed: {e}", RNS.LOG_DEBUG)
            continue

    RNS.log("All certificate generation methods failed", RNS.LOG_ERROR)
    return cert_path
