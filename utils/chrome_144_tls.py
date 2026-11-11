import asyncio
from wreq.tls import (
    TlsOptions,
    TlsVersion,
    AlpnProtocol,
    AlpsProtocol,
    CertificateCompressionAlgorithm,
    ExtensionType,
)


def chrome_144_tls():
    # 1. Define the exact cipher suite order
    ciphers = [
        "TLS_AES_128_GCM_SHA256",
        "TLS_AES_256_GCM_SHA384",
        "TLS_CHACHA20_POLY1305_SHA256",
        "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
        "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
        "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
        "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
        "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
        "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
        "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA",
        "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA",
        "TLS_RSA_WITH_AES_128_GCM_SHA256",
        "TLS_RSA_WITH_AES_256_GCM_SHA384",
        "TLS_RSA_WITH_AES_128_CBC_SHA",
        "TLS_RSA_WITH_AES_256_CBC_SHA",
    ]

    # 2. Define signature algorithms
    sigalgs = [
        "ecdsa_secp256r1_sha256",
        "rsa_pss_rsae_sha256",
        "rsa_pkcs1_sha256",
        "ecdsa_secp384r1_sha384",
        "rsa_pss_rsae_sha384",
        "rsa_pkcs1_sha384",
        "rsa_pss_rsae_sha512",
        "rsa_pkcs1_sha512",
    ]

    # 3. Define supported curves (groups)
    curves = [
        "X25519MLKEM768",
        "X25519",
        "P-256",
        "P-384",
    ]

    # 4. Define the exact extension order
    # Note: GREASE extensions are inserted automatically by rnet/boringssl
    extensions = [
        ExtensionType.SESSION_TICKET,  # 35
        ExtensionType.CERTIFICATE_TIMESTAMP,  # 18
        ExtensionType.STATUS_REQUEST,  # 5
        ExtensionType.CERT_COMPRESSION,  # 27
        ExtensionType.PSK_KEY_EXCHANGE_MODES,  # 45
        ExtensionType.KEY_SHARE,  # 51
        ExtensionType.EC_POINT_FORMATS,  # 11
        ExtensionType.SUPPORTED_GROUPS,  # 10
        ExtensionType.SERVER_NAME,  # 0
        ExtensionType.SUPPORTED_VERSIONS,  # 43
        ExtensionType.APPLICATION_SETTINGS_NEW,  # 17613 (New codepoint)
        ExtensionType.RENEGOTIATE,  # 65281
        ExtensionType.ENCRYPTED_CLIENT_HELLO,  # 65037 (ECH)
        ExtensionType.APPLICATION_LAYER_PROTOCOL_NEGOTIATION,  # 16
        ExtensionType.EXTENDED_MASTER_SECRET,  # 23
        ExtensionType.SIGNATURE_ALGORITHMS,  # 13
    ]

    # 5. Configure TlsOptions
    tls_options = TlsOptions(
        cipher_list=":".join(ciphers),
        sigalgs_list=":".join(sigalgs),
        curves_list=":".join(curves),
        min_tls_version=TlsVersion.TLS_1_2,
        max_tls_version=TlsVersion.TLS_1_3,
        alpn_protocols=[AlpnProtocol.HTTP2, AlpnProtocol.HTTP1],

        # ALPS configuration for id 17613
        alps_protocols=[AlpsProtocol.HTTP2],
        alps_use_new_codepoint=True,

        # Certificate compression
        certificate_compression_algorithms=[CertificateCompressionAlgorithm.BROTLI],

        # Specific extensions
        enable_ocsp_stapling=True,  # status_request (5)
        enable_signed_cert_timestamps=True,  # signed_certificate_timestamp (18)
        renegotiation=True,  # extensionRenegotiationInfo (65281)
        enable_ech_grease=True,  # extensionEncryptedClientHello (65037)
        grease_enabled=True,  # TLS_GREASE
        psk_dhe_ke=True,  # psk_key_exchange_modes (45)
        session_ticket=True,  # session_ticket (35)

        # Apply the extension permutation
        extension_permutation=extensions,
        permute_extensions=False,
    )

    # Create client with custom TLS options
    # verify=False is used here to bypass local certificate issues during testing,
    # but you should configure a CertStore for production use.
    return tls_options
    # client = Client(tls_options=tls_options, tls_info=True, verify=False)
    #
    # print("Sending request to tls.peet.ws...")
    # try:
    #     resp = await client.get("https://tls.peet.ws/api/all")
    #     print(await resp.text())
    # except Exception as e:
    #     print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
