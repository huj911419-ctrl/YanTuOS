#!/usr/bin/env python3
"""Create project-local certificates. Never installs a CA into any trust store."""

import argparse
import ipaddress
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("ip", help="Ubuntu 的私有局域网 IP，证书必须与访问地址匹配")
parser.add_argument(
    "--output", type=Path, default=Path(__file__).resolve().parents[1] / ".runtime/tls"
)
args = parser.parse_args()
try:
    address = ipaddress.ip_address(args.ip)
    if not address.is_private or address.is_unspecified:
        raise ValueError("只能为本机或私有局域网 IP 生成证书。")
    if args.output.exists():
        raise ValueError("输出目录已存在，拒绝覆盖现有证书。")
    args.output.mkdir(parents=True, mode=0o700)

    def run(*command):
        subprocess.run(
            ["openssl", *command], cwd=args.output, check=True, capture_output=True
        )

    run(
        "req",
        "-x509",
        "-newkey",
        "rsa:3072",
        "-nodes",
        "-days",
        "3650",
        "-sha256",
        "-keyout",
        "ca.key",
        "-out",
        "ca.crt",
        "-subj",
        "/CN=YanTu OS Local CA",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
    )
    run(
        "req",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        "server.key",
        "-out",
        "server.csr",
        "-subj",
        "/CN=" + args.ip,
    )
    (args.output / "server.ext").write_text(
        "subjectAltName=IP:"
        + args.ip
        + "\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n"
    )
    run(
        "x509",
        "-req",
        "-in",
        "server.csr",
        "-CA",
        "ca.crt",
        "-CAkey",
        "ca.key",
        "-CAcreateserial",
        "-out",
        "server.crt",
        "-days",
        "365",
        "-sha256",
        "-extfile",
        "server.ext",
    )
    run("verify", "-CAfile", "ca.crt", "server.crt")
    for f in args.output.iterdir():
        f.chmod(0o600)
    print("证书已生成并通过 OpenSSL 校验：", args.output.resolve())
    print(
        "没有修改系统或手机信任设置。只将 ca.crt 传给自己的设备；不要分享任何 .key 文件。"
    )
except (ValueError, OSError, subprocess.CalledProcessError) as exc:
    parser.exit(1, "证书生成失败：" + str(exc) + "\n")
