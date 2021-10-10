import hashlib

def verify_secret_token(secret_config, token : str):
    if token == None:
        return False
        
    hashed_token = hashlib.sha256(token.encode('utf-8')).hexdigest()
    return hashed_token == secret_config["hashed_token"]