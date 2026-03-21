key = b"changeme"
bucket = "my-aws-storage-bucket"
zipFilenamePrepend = "furizon_gallery_"

import time
import json
import hmac
import boto3
import base64
import hashlib
from datetime import datetime
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from stream_zip import stream_zip, ZIP_64

app = FastAPI()

s3_client = boto3.client('s3')

def generate_zip_stream(files: list):
    """
    Generator that yields chunks of the resulting ZIP file.
    """
    def member_files():
        for file in files:

            response = s3_client.get_object(Bucket=bucket, Key=file["k"])
            s3_stream = response['Body']
            
            def file_chunks():
                for chunk in s3_stream.iter_chunks(chunk_size=65536):
                    yield chunk
            
            yield (
                file["nf"],                             # Filename
                datetime.fromisoformat(file["t"]),      # Timestamp for the file inside the zip
                0o600,                                  # File permissions inside the zip
                ZIP_64,                                 # Zip format
                file_chunks()                           # The streaming data from S3
            )

    for zipped_chunk in stream_zip(member_files()):
        yield zipped_chunk

@app.post("/d")
async def bulkDownload(request: Request, mac: str):
    data = await request.body()
    data = base64.b64decode(data)
    mac = bytes.fromhex(mac)
    computed = hmac.new(key, data, hashlib.sha256).digest()
    if computed != mac:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"error": "Invalid HMAC"})
    
    data = json.loads(data)
    if int(time.time() * 1000) > data["expireMs"]:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"error": "Request expired"})
    
    # TODO CHECK IF SAME USER IS NOT ALREADY DOWNLOADING OTHER FILES
    
    return StreamingResponse(
        generate_zip_stream(data["files"]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zipFilenamePrepend}{int(time.time())}.zip"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8083)
