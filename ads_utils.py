import os
import hashlib
import requests


def _get_snapchat_access_token() -> str:
    url = "https://accounts.snapchat.com/login/oauth2/access_token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": os.getenv("SNAPCHAT_ADS_REFRESH_TOKEN"),
        "client_id": os.getenv("SNAPCHAT_ADS_CLIENT_ID"),
        "client_secret": os.getenv("SNAPCHAT_ADS_CLIENT_SECRET"),
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["access_token"]


def upload_to_meta(file_path: str, file_type: str) -> dict:
    access_token = os.getenv("META_ADS_ACCESS_TOKEN")
    ad_account_id = os.getenv("META_ADS_ACCOUNT_ID")
    if file_type == "video":
        url = f"https://graph-video.facebook.com/v18.0/{ad_account_id}/advideos"
        with open(file_path, "rb") as f:
            response = requests.post(
                url,
                data={"access_token": access_token},
                files={"source": f}
            )
    else:
        url = f"https://graph.facebook.com/v18.0/{ad_account_id}/adimages"
        with open(file_path, "rb") as f:
            response = requests.post(
                url,
                data={"access_token": access_token},
                files={"filename": f}
            )
    response.raise_for_status()
    return response.json()


def upload_to_snapchat(file_path: str, file_type: str) -> dict:
    access_token = _get_snapchat_access_token()
    ad_account_id = os.getenv("SNAPCHAT_ADS_AD_ACCOUNT_ID")
    headers = {"Authorization": f"Bearer {access_token}"}

    # Create Media Object
    create_url = f"https://adsapi.snapchat.com/v1/adaccounts/{ad_account_id}/media"
    media_data = {
        "media": [
            {
                "name": os.path.basename(file_path),
                "type": "VIDEO" if file_type == "video" else "IMAGE",
                "ad_account_id": ad_account_id,
            }
        ]
    }
    create_res = requests.post(create_url, headers=headers, json=media_data)
    create_res.raise_for_status()
    media_id = create_res.json()["media"][0]["media"]["id"]

    # Upload File
    upload_url = f"https://adsapi.snapchat.com/v1/media/{media_id}/upload"
    with open(file_path, "rb") as f:
        upload_res = requests.post(upload_url, headers=headers, files={"file": f})
    upload_res.raise_for_status()
    return upload_res.json()


def upload_to_tiktok(file_path: str) -> dict:
    access_token = os.getenv("TIKTOK_ADS_ACCESS_TOKEN")
    advertiser_id = os.getenv("TIKTOK_ADS_ADVERTISER_ID")
    url = "https://business-api.tiktok.com/open_api/v1.3/file/video/ad/upload/"
    headers = {"Access-Token": access_token}

    with open(file_path, "rb") as f:
        video_signature = hashlib.md5(f.read()).hexdigest()

    data = {
        "advertiser_id": advertiser_id,
        "video_signature": video_signature,
        "video_name": os.path.basename(file_path),
    }
    with open(file_path, "rb") as f:
        response = requests.post(url, headers=headers, data=data, files={"video_file": f})
    response.raise_for_status()
    return response.json()
