import subprocess
import os
import sys
import grpc

from threecities.v1.verifier_pb2 import SayRequest
from threecities.v1.verifier_pb2_grpc import VerifierServiceStub

# get_grpc_ca_root_cert_file_path returns the file path of the
# additional CA certificate required to verify our self-signed
# certificate to run grpc with SSL. grpc requires SSL, even over
# localhost. Our strategy to satisfy this requirement is to follow the
# instructions here
# https://connectrpc.com/docs/node/getting-started/#use-the-grpc-protocol-instead-of-the-connect-protocol,
# which are roughly 1. one-time setup to create a self-signed
# certificate via `mkcert` and install it in the local CA root, 2. tell
# the python grpc client where to find the additional CA root
# certificate so that our self-signed certificate is verifiable. There
# are three ways to tell python where to find the addition CA root
# certificate: (i) run `mkcert -CAROOT` in a subshell, (ii) provide the
# env THREECITIES_GRPC_CA_ROOT_CERT="$(mkcert -CAROOT)/rootCA.pem", or
# (iii) set GRPC_DEFAULT_SSL_ROOTS_FILE_PATH="$(mkcert
# -CAROOT)/rootCA.pem"
# https://grpc.github.io/grpc/cpp/grpc__security__constants_8h.html#a48565da473b7c82fa2453798f620fd59
# --> we implement (i) and (ii) here.
def get_grpc_ca_root_cert_file_path():
    # Try to execute the subshell command and get the path
    try:
        # Run the mkcert command and capture the output
        completed_process = subprocess.run(
            ["mkcert", "-CAROOT"], capture_output=True, check=True, text=True)
        ca_root_path = completed_process.stdout.strip()
        grpc_ca_root_cert_file_path = os.path.join(ca_root_path, "rootCA.pem")
    except subprocess.CalledProcessError:
        # If the subshell command fails, fall back to the environment variable
        grpc_ca_root_cert_file_path = os.getenv("THREECITIES_GRPC_CA_ROOT_CERT")

    # If neither method provides a path, exit with a fatal error
    if not grpc_ca_root_cert_file_path:
        sys.exit("Fatal Error: Could not determine gRPC CA root cert file path.")

    return grpc_ca_root_cert_file_path

grpc_ca_root_cert_file_path = get_grpc_ca_root_cert_file_path()

with open(grpc_ca_root_cert_file_path, 'rb') as f:
    root_cert = f.read()
channel_credentials = grpc.ssl_channel_credentials(root_cert)
channel = grpc.secure_channel("127.0.0.1:8443", channel_credentials) # TODO configurable grpc endpoint
stub = VerifierServiceStub(channel)

def verify_payment(): # TODO real request type and implementation
    say_response = stub.Say(SayRequest(sentence="Hello there!"))
    print("grpc server stub response: " + say_response.sentence)
    return True # TODO real response type
