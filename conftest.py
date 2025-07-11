config.yaml

pgp_public_key: "${WORKSPACE}/bu-digital-paymentor-qa-automation/utils/file-public.pgp"
csv_data_dir: "${WORKSPACE}/bu-digital-paymentor-qa-automation/data"
encryption_dir: "${WORKSPACE}/bu-digital-paymentor-qa-automation/encryption"
cloudwatch:
  log_groups:
  gatekeeper: "/aws/lambda/sb-utp1-1674e330-etl_gatekeeper"
  primary: "/aws/lambda/sb-utp1-1674e330-etl_primary"
  primary_batch_sender: "/aws/lambda/sb-utp1-1674e330-etl_primary_batch_sender"



pages/test_encrypt.py

import os
import glob
import yaml
import pgpy

class PageEncrypt:
    def __init__(self, config):
        self.key_file = config['pgp_public_key']
        self.csv_dir = config['csv_data_dir']
        self.enc_dir = config['encryption_dir']
        self.file_list = glob.glob(os.path.join(self.csv_dir, "*.csv"))
        
    @classmethod
    def load_config(cls):
        workspace_root = os.environ.get('WORKSPACE', os.getcwd())
        config_path = os.path.join(workspace_root, 'bu-digital-paymentor-qa-automation', 'config.yaml')
        with open(config_path) as f:
            raw_config = yaml.safe_load(f)

    # Expand env vars like ${WORKSPACE} in all values
        resolved_config = {
            key: os.path.expandvars(value) if isinstance(value, str) else value
            for key, value in raw_config.items()
        }

        return resolved_config


    def public_key_exists(self):
        return os.path.isfile(self.key_file)

    def has_csv_files(self):
        return len(self.file_list) > 0

    def encrypt_all_csvs(self):
        pubkey, _ = pgpy.PGPKey.from_file(self.key_file)
        if not os.path.exists(self.enc_dir):
            os.makedirs(self.enc_dir)
        encrypted_files = []
        for file_path in self.file_list:
            msg = pgpy.PGPMessage.new(file_path, file=True)
            encrypted_msg = pubkey.encrypt(msg)
            encrypted_str = str(encrypted_msg)
            base_name = os.path.basename(file_path)

           # Set the encryption directory directly
    #self.enc_dir = r"C:\Users\aitha253418\PayMentor\encryption"
            encrypted_file_path = os.path.join(self.enc_dir, base_name + ".gpg")
            with open(encrypted_file_path, 'w') as f:
                f.write(encrypted_str)
            encrypted_files.append(encrypted_file_path)
        return encrypted_files

    def verify_encrypted_files(self, encrypted_files):
        # Returns a list of missing encrypted files (should be empty if all are present)
        missing = []
        for file_path in self.file_list:
            base_name = os.path.basename(file_path)
            encrypted_file = os.path.join(self.enc_dir, base_name + ".gpg")
            if not os.path.isfile(encrypted_file):
                missing.append(encrypted_file)
        return missing


steps/test_encrypt_steps.py

import pytest
from pytest_bdd import scenarios, given, when, then
from pages.test_encrypt import PageEncrypt


# Load all scenarios from the feature file
scenarios('../features/encrypt_csv.feature')

@pytest.fixture(scope="session")
def config():
    return PageEncrypt.load_config()

@pytest.fixture
def context(config):
    # Provide a fresh PageEncrypt instance for each test
    return {
        'page': PageEncrypt(config),
        'encrypted_files': []
    }

@given("the public PGP key file exists")
def public_pgp_key_exists(context):
    #assert context['page'].public_key_exists(), \
        f"Public key file {context['page'].key_file} does not exist."
    
@when("I encrypt all the CSV files using the public key")
def encrypt_csv_files(context):
    context['encrypted_files'] = context['page'].encrypt_all_csvs()

@then('encrypted files should be created in the encryption directory with ".gpg" extension')
def encrypted_files_created(context):
    missing = context['page'].verify_encrypted_files(context['encrypted_files'])
    assert not missing, f"Missing encrypted files: {', '.join(missing)}"


so this is the whole thing chatgpt, as you see, we have config.yaml where this is defined: pgp_public_key: "${WORKSPACE}/bu-digital-paymentor-qa-automation/utils/file-public.pgp"
then , this is being called in test_encrypt.py and then test_encrypt.py is called in test_encrypt_steps.py



