"""
Utility functions to retrieve information about available services and setting up security for the Hops platform.

These utils facilitates development by hiding complexity for programs interacting with Hops services.
"""

import jks
import string
import base64
import textwrap
from hops import constants
import os

def get_key_store():
    """
    Get keystore location

    Returns:
        keystore filename
    """
    return constants.SSL_CONFIG.K_CERTIFICATE_CONFIG


def get_trust_store():
    """
    Get truststore location

    Returns:
         truststore filename
    """
    return constants.SSL_CONFIG.T_CERTIFICATE_CONFIG


def _get_cert_pw():
    """
    Get keystore password from local container

    Returns:
        Certificate password
    """
    pwd_path = os.getcwd() + "/" + constants.SSL_CONFIG.CRYPTO_MATERIAL_PASSWORD

    if not os.path.exists(pwd_path):
        raise AssertionError('material_passwd is not present in directory: {}'.format(pwd_path))

    with open(pwd_path) as f:
        key_store_pwd = f.read()

    # remove special characters (due to bug in password materialized, should not be necessary when the bug is fixed)
    key_store_pwd = "".join(list(filter(lambda x: x in string.printable and not x == "@", key_store_pwd)))
    return key_store_pwd


def get_key_store_cert():
    """
    Get keystore certificate from local container

    Returns:
        Certificate password
    """
    cert_path = os.getcwd() + "/" + constants.SSL_CONFIG.K_CERTIFICATE_CONFIG

    if not os.path.exists(cert_path):
        raise AssertionError('k_certificate is not present in directory: {}'.format(cert_path))

    # read as bytes, don't try to use utf-8 encoding
    with open(cert_path, "rb") as f:
        key_store_cert = f.read()
        key_store_cert = base64.b64encode(key_store_cert)

    return key_store_cert


def get_key_store_pwd():
    """
    Get keystore password

    Returns:
         keystore password
    """
    return _get_cert_pw()


def get_trust_store_pwd():
    """
    Get truststore password

    Returns:
         truststore password
    """
    return _get_cert_pw()


def bytes_to_pem_str(der_bytes, pem_type):
    """
    Utility function for creating PEM files

    Args:
    :der_bytes: DER encoded bytes
    :pem_type: type of PEM, e.g Certificate, Private key, or RSA private key

    Returns:
         PEM String for a DER-encoded certificate or private key
    """
    pem_str = ""
    pem_str = pem_str + "-----BEGIN {}-----".format(pem_type) + "\n"
    pem_str = pem_str + "\r\n".join(textwrap.wrap(base64.b64encode(der_bytes).decode('ascii'), 64)) + "\n"
    pem_str = pem_str + "-----END {}-----".format(pem_type) + "\n"
    return pem_str


def convert_jks_to_pem(jks_path, pw):
    """
    Converts a JKS to a PEM string

    Args:
    :jks_path: path to the JKS file
    :pw: password for decrypting the JKS file

    Returns:
         PEM string
    """
    # load the keystore and decrypt it with password
    ks = jks.KeyStore.load(jks_path, pw, try_decrypt_keys=True)
    pem_str = ""
    # Convert private keys and their certificate into PEM format and append to string
    for alias, pk in ks.private_keys.items():
        if pk.algorithm_oid == jks.util.RSA_ENCRYPTION_OID:
            pem_str = pem_str + bytes_to_pem_str(pk.pkey, "RSA PRIVATE KEY")
        else:
            pem_str = pem_str + bytes_to_pem_str(pk.pkey_pkcs8, "PRIVATE KEY")
        for c in pk.cert_chain:
            # c[0] contains type of cert, i.e X.509
            pem_str = pem_str + bytes_to_pem_str(c[1], "CERTIFICATE")

    # Convert CA Certificates into PEM format and append to string
    for alias, c in ks.certs.items():
        pem_str = pem_str + bytes_to_pem_str(c.cert, "CERTIFICATE")
    return pem_str

def write_pem(jks_path, pw, output_path):
    """
    Converts a JKS file into a PEM string and writes it to a file

    Args:
    :jks_path: path to the JKS file
    :pw: password for decrypting the JKS file
    :output_path: path to write the PEM file

    """
    pem_str = convert_jks_to_pem(jks_path, pw)
    with open(output_path, "w") as f:
        f.write(pem_str)

def write_pems():
    """
    Converts JKS files into PEM to be compatible with Python libraries
    """
    k_jks_path = os.getcwd() + "/" + constants.SSL_CONFIG.K_CERTIFICATE_CONFIG
    t_jks_path = os.getcwd() + "/" + constants.SSL_CONFIG.T_CERTIFICATE_CONFIG
    k_pem_path = os.getcwd() + "/" + constants.SSL_CONFIG.PEM_K_CERTIFICATE_CONFIG
    t_pem_path = os.getcwd() + "/" + constants.SSL_CONFIG.PEM_T_CERTIFICATE_CONFIG
    write_pem(k_jks_path, get_key_store_pwd(), k_pem_path)
    write_pem(t_jks_path, get_trust_store_pwd(), t_pem_path)

def get_ca_certificate_location():
    """
    Get location of trusted CA certificate (server.pem) for 2-way TLS authentication with Kafka cluster

    Returns:
        string path to ca certificate (server.pem)
    """
    raise NotImplementedError

def get_client_key_location():
    """
    Get location of client private key (client.key) for 2-way TLS authentication with Kafka cluster

    Returns:
        string path to client private key (client.key)
    """
    raise NotImplementedError

def get_client_certificate_location():
    """
    Get location of client certificate (client.pem) for 2-way TLS authentication with Kafka cluster

    Returns:
         string path to client certificate (client.pem)
    """
    raise NotImplementedError