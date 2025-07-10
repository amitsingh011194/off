Like you helped me herew:

for file_name in file_names:
     
        workspace_root = os.environ.get('WORKSPACE', os.getcwd())
        encryption_dir = os.path.join(workspace_root, 'bu-digital-paymentor-qa-automation', 'encryption')

        # Create the directory if it doesn't exist
        os.makedirs(encryption_dir, exist_ok=True)

        # Build the full file path
        local_path = os.path.join(encryption_dir, file_name)

earlier it was:

   local_path = os.path.join(local_dir, file_name)


Now I  need help with updating this part of the code as well in the same file:

@when('the user uploads 7 PGP-encrypted files to "<inbound_bucket>"')
def user_uploads_encrypted_files(config):
    current_date = datetime.now().strftime('%Y%m%d')
    local_dir = r"C:\Users\aitha253418\PayMentor_Docker\encryption"
    bucket = config['inbound_bucket']
    profile = 'qa'

I mean the path, thats al.
