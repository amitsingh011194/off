@given('AWS credentials are refreshed for profile "qa"')
def aws_credentials_refreshed():
    subprocess.run(["aws", "sso", "login", "--profile", "qa"], check=True)

@when('the user uploads 7 PGP-encrypted files to "<inbound_bucket>"')
def user_uploads_encrypted_files(config):
    current_date = datetime.now().strftime('%Y%m%d')
    # Dynamically get the workspace root
    workspace_root = os.environ.get('WORKSPACE', os.getcwd())
    
    # Point to the 'encryption' directory under your project path
    local_dir = os.path.join(workspace_root, 'bu-digital-paymentor-qa-automation', 'encryption')
    
    bucket = config['inbound_bucket']
    profile = 'qa'
    file_names = [
        f"CoBorrowerData_{current_date}_090735.csv.gpg",
        f"CustomerData_{current_date}_085342.csv.gpg",
        f"LoanInformation_{current_date}_083426.csv.gpg",
        f"LoanProfile_{current_date}_082748.csv.gpg",
        f"sfcEXLReconciliation_{current_date}_090028.csv.gpg",
        f"SSPLogin_{current_date}_084727.csv.gpg",
        f"PaymentData_{current_date}_084059.csv.gpg"
    ]
    if bucket.endswith('/'):
        bucket = bucket[:-1]
