
import os
import requests
import hashlib

def upload_to_meta(file_path, file_type):
    """Uploads a file to Meta Ads Manager."""
    access_token = os.getenv("META_ADS_ACCESS_TOKEN")
    ad_account_id = os.getenv("META_ADS_ACCOUNT_ID")
    
    if file_type == "video":
        url = f"https://graph.facebook.com/v19.0/{ad_account_id}/advideos"
    else:
        url = f"https://graph.facebook.com/v19.0/{ad_account_id}/adimages"
        
    files = {'file': open(file_path, 'rb')}
    params = {'access_token': access_token}
    
    response = requests.post(url, params=params, files=files)
    return response.json()

def upload_to_snapchat(file_path, file_type):
    """Uploads a file to Snapchat Ads Manager."""
    # 1. Get Access Token (assuming refresh token flow)
    # 2. Create Media Object
    # 3. Upload File
    # This is a simplified version
    ad_account_id = os.getenv("SNAPCHAT_ADS_AD_ACCOUNT_ID")
    access_token = os.getenv("SNAPCHAT_ADS_ACCESS_TOKEN") # Should be refreshed
    
    # Create Media
    create_url = f"https://adsapi.snapchat.com/v1/adaccounts/{ad_account_id}/media"
    headers = {"Authorization": f"Bearer {access_token}"}
    media_data = {
        "media": [{
            "name": os.path.basename(file_path),
            "type": "VIDEO" if file_type == "video" else "IMAGE",
            "ad_account_id": ad_account_id
        }]
    }
    
    create_res = requests.post(create_url, headers=headers, json=media_data).json()
    media_id = create_res['result'][0]['id']
    
    # Upload File
    upload_url = f"https://adsapi.snapchat.com/v1/media/{media_id}/upload"
    files = {'file': open(file_path, 'rb')}
    upload_res = requests.post(upload_url, headers=headers, files=files).json()
    
    return upload_res

def upload_to_tiktok(file_path):
    """Uploads a video to TikTok Ads Manager."""
    access_token = os.getenv("TIKTOK_ADS_ACCESS_TOKEN")
    advertiser_id = os.getenv("TIKTOK_ADS_ADVERTISER_ID")
    
    url = "https://business-api.tiktok.com/open_api/v1.3/file/video/ad/upload/"
    headers = {"Access-Token": access_token}
    
    # Calculate MD5 signature
    with open(file_path, 'rb') as f:
        file_content = f.read()
        video_signature = hashlib.md5(file_content).hexdigest()
        
    data = {
        "advertiser_id": advertiser_id,
        "video_signature": video_signature
    }
    files = {"video_file": open(file_path, 'rb')}
    
    response = requests.post(url, headers=headers, data=data, files=files)
    return response.json()
