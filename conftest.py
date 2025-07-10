pages/test_encrypt.py


here we have this:

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
        # Assumes this file is in pages/, config.yaml is two levels up
        workspace_root = os.environ.get('WORKSPACE', os.getcwd())
        config_path = os.path.join(workspace_root, 'bu-digital-paymentor-qa-automation', 'config.yaml')
        with open(config_path) as f:
            return yaml.safe_load(f)

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


