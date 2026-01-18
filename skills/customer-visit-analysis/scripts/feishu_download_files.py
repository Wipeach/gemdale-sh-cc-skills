"""
Feishu File Downloader
Lists and downloads files from a Feishu folder using the Feishu API.

API Reference:
- List files: GET /drive/v1/files?folder_token={token}
- Download file: GET /drive/v1/files/{file_token}/download
- File metadata: GET /drive/v1/files/{file_token}
- Export task (for docs): POST /drive/v1/export_tasks

Usage:
    python feishu_download_files.py <folder_token> [output_dir]

Example:
    python feishu_download_files.py DR8cfYq3XlTzq6d00r0cCq5rnDb
    python feishu_download_files.py DR8cfYq3XlTzq6d00r0cCq5rnDb ./my-output
"""
import os
import sys
import time
import argparse
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from project root
load_dotenv()

# Configuration from .env
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
DEFAULT_OUTPUT_DIR = "./feishu-download-file"

# Feishu API endpoints
API_BASE = "https://open.feishu.cn/open-apis"
AUTH_URL = f"{API_BASE}/auth/v3/tenant_access_token/internal"
FILE_LIST_URL = f"{API_BASE}/drive/v1/files"
FILE_DOWNLOAD_URL = f"{API_BASE}/drive/v1/files"
FILE_META_URL = f"{API_BASE}/drive/v1/files"
EXPORT_TASK_URL = f"{API_BASE}/drive/v1/export_tasks"

# File type to extension mapping
TYPE_TO_EXT = {
    "docx": ".docx",
    "doc": ".doc",
    "xlsx": ".xlsx",
    "xls": ".xls",
    "pptx": ".pptx",
    "ppt": ".ppt",
    "pdf": ".pdf",
    "txt": ".txt",
    "jpg": ".jpg",
    "jpeg": ".jpg",
    "png": ".png",
    "gif": ".gif",
    "bmp": ".bmp",
    "mp4": ".mp4",
    "mp3": ".mp3",
    "zip": ".zip",
    "rar": ".rar",
}


def get_tenant_access_token():
    """Get tenant access token for Feishu API."""
    response = requests.post(
        AUTH_URL,
        json={
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }
    )
    response.raise_for_status()
    data = response.json()
    if data.get("code") != 0:
        raise Exception(f"Failed to get access token: {data.get('msg')}")
    return data.get("tenant_access_token")


def get_headers(token):
    """Generate headers with authorization token."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def sanitize_filename(name):
    """Sanitize filename for safe file system usage."""
    # Replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    # Remove control characters
    name = ''.join(char for char in name if ord(char) >= 32)
    return name.strip() or "unnamed_file"


def list_files_in_folder(token, folder_token):
    """List all files in a Feishu folder."""
    files = []
    page_token = ""

    while True:
        params = {
            "folder_token": folder_token,
            "page_size": 50
        }
        if page_token:
            params["page_token"] = page_token

        response = requests.get(
            FILE_LIST_URL,
            headers=get_headers(token),
            params=params
        )
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"Failed to list files: {data.get('msg')} - Response: {data}")

        files_data = data.get("data", {})
        items = files_data.get("files", [])
        files.extend(items)

        has_more = files_data.get("has_more", False)
        if not has_more:
            break
        page_token = files_data.get("page_token", "")

    return files


def get_file_download_url(token, file_token):
    """Get the download URL for a file."""
    response = requests.get(
        f"{FILE_DOWNLOAD_URL}/{file_token}/download",
        headers=get_headers(token)
    )
    response.raise_for_status()
    data = response.json()

    if data.get("code") != 0:
        raise Exception(f"Failed to get download URL: {data.get('msg')}")

    return data.get("data", {}).get("url")


def get_file_metadata(token, file_token):
    """Get metadata for a file."""
    response = requests.get(
        f"{FILE_META_URL}/{file_token}",
        headers=get_headers(token)
    )
    response.raise_for_status()
    data = response.json()

    if data.get("code") != 0:
        raise Exception(f"Failed to get file metadata: {data.get('msg')}")

    return data.get("data", {})


def download_file(url, output_path):
    """Download file from URL to output path."""
    response = requests.get(url, stream=True)
    response.raise_for_status()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


def create_export_task(token, file_token, file_type, file_extension=""):
    """Create an export task for a Feishu document (docx, xlsx, etc.)."""
    payload = {
        "token": file_token,
        "type": file_type,
    }
    if file_extension:
        payload["file_extension"] = file_extension

    response = requests.post(
        EXPORT_TASK_URL,
        headers=get_headers(token),
        json=payload
    )
    response.raise_for_status()
    data = response.json()

    if data.get("code") != 0:
        raise Exception(f"Failed to create export task: {data.get('msg')}")

    return data.get("data", {}).get("ticket")


def query_export_task(token, ticket, file_token, max_wait=60):
    """Query export task status and return the export file token when ready."""
    start_time = time.time()

    while time.time() - start_time < max_wait:
        response = requests.get(
            f"{EXPORT_TASK_URL}/{ticket}?token={file_token}",
            headers=get_headers(token)
        )
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"Failed to query export task: {data.get('msg')}")

        result = data.get("data", {}).get("result", {})
        job_status = result.get("job_status")

        # job_status: 0 = success, 1 = processing, 2 = failed
        if job_status == 0:
            # Export complete, return the file token
            return result.get("file_token")
        elif job_status == 2:
            raise Exception(f"Export task failed: {result.get('job_error_msg')}")
        elif job_status is None:
            # Older API format - check for task_status
            task_status = data.get("data", {}).get("task_status")
            if task_status == "done":
                return data.get("data", {}).get("result", {}).get("file_token")
            elif task_status == "failed":
                raise Exception("Export task failed")

        # Still processing, wait and retry
        time.sleep(1)

    raise Exception("Export task timed out")


def download_exported_file(token, export_file_token, output_path):
    """Download an exported file using the export file token."""
    response = requests.get(
        f"{API_BASE}/drive/v1/export_tasks/file/{export_file_token}/download",
        headers=get_headers(token)
    )
    response.raise_for_status()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


def process_file(token, file_info, output_dir):
    """Process a single file: download and save appropriately."""
    file_token = file_info.get("token")
    file_name = sanitize_filename(file_info.get("name", f"file_{file_token}"))
    file_type = file_info.get("type", "")

    print(f"  Processing: {file_name} (type: {file_type})")

    # Check if it's a folder
    if file_type == "folder":
        # Create subdirectory and process its contents
        sub_dir = output_dir / file_name
        sub_dir.mkdir(parents=True, exist_ok=True)
        print(f"    -> Entering folder: {sub_dir}")

        try:
            sub_files = list_files_in_folder(token, file_token)
            for sub_file in sub_files:
                process_file(token, sub_file, sub_dir)
        except Exception as e:
            print(f"    -> Error processing folder: {e}")
        return

    # Determine file extension
    extension = TYPE_TO_EXT.get(file_type.lower(), "")
    if not extension and file_name:
        # Try to get from existing filename
        ext = Path(file_name).suffix
        if ext:
            extension = ext
        else:
            extension = ".bin"

    # Ensure filename has extension
    if not file_name.lower().endswith(extension.lower()):
        file_name = file_name + extension

    output_path = output_dir / file_name

    # Handle file download
    try:
        # Feishu documents (doc, docx, sheet, xlsx, etc.) need export task API
        if file_type.lower() in ["doc", "docx", "xlsx", "xls", "pptx", "ppt", "pdf", "sheet", "slide", "bitable"]:
            print(f"    -> Using export task API for {file_type} file...")
            # Remove leading dot from extension for the API
            ext_for_api = extension.lstrip('.') if extension else file_type
            ticket = create_export_task(token, file_token, file_type, ext_for_api)
            export_file_token = query_export_task(token, ticket, file_token)
            download_exported_file(token, export_file_token, output_path)
            print(f"    -> Exported and downloaded to: {output_path}")

        elif file_type in ["jpg", "jpeg", "png", "gif", "bmp", "mp4", "mp3", "zip", "rar"]:
            # Binary files - use direct download API
            download_url = get_file_download_url(token, file_token)
            download_file(download_url, output_path)
            print(f"    -> Downloaded to: {output_path}")

        else:
            # For unknown types, try direct download first
            try:
                download_url = get_file_download_url(token, file_token)
                download_file(download_url, output_path)
                print(f"    -> Downloaded to: {output_path}")
            except Exception as e:
                print(f"    -> Failed to download using download API: {e}")

                # Try export task as fallback
                try:
                    print(f"    -> Trying export task API as fallback...")
                    ext_for_api = extension.lstrip('.') if extension else file_type
                    ticket = create_export_task(token, file_token, file_type, ext_for_api)
                    export_file_token = query_export_task(token, ticket, file_token)
                    download_exported_file(token, export_file_token, output_path)
                    print(f"    -> Exported and downloaded to: {output_path}")
                except Exception as export_error:
                    print(f"    -> Export task also failed: {export_error}")

    except Exception as e:
        print(f"    -> Error processing file: {e}")


def main():
    """Main function to list and download files from Feishu folder."""
    parser = argparse.ArgumentParser(
        description="Download files from a Feishu folder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python feishu_download_files.py DR8cfYq3XlTzq6d00r0cCq5rnDb
  python feishu_download_files.py DR8cfYq3XlTzq6d00r0cCq5rnDb ./my-output
        """
    )
    parser.add_argument("folder_token", help="Feishu folder token to download from")
    parser.add_argument("output_dir", nargs="?", default=DEFAULT_OUTPUT_DIR,
                        help="Output directory (default: ./feishu-download-file)")
    args = parser.parse_args()

    folder_token = args.folder_token
    output_dir = Path(args.output_dir)

    print("Feishu File Downloader")
    print("=" * 50)

    # Check credentials
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("Error: FEISHU_APP_ID and FEISHU_APP_SECRET must be set in .env file")
        sys.exit(1)

    # Get access token
    print("Getting access token...")
    token = get_tenant_access_token()
    print(f"Access token obtained: {token[:20]}...")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # List files in folder
    print(f"\nListing files in folder: {folder_token}")
    files = list_files_in_folder(token, folder_token)

    print(f"\nFound {len(files)} item(s):")
    for i, file_info in enumerate(files, 1):
        name = file_info.get("name")
        file_type = file_info.get("type")
        file_token = file_info.get("token")
        print(f"  {i}. [{file_type.upper() if file_type else 'UNKNOWN'}] {name} (token: {file_token})")

    # Download files
    print(f"\nDownloading files to: {output_dir}")
    print("-" * 50)

    for file_info in files:
        process_file(token, file_info, output_dir)

    print("\n" + "=" * 50)
    print("Download complete!")


if __name__ == "__main__":
    main()
