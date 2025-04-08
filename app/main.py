import os

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.ContentModel import is_supported_mime_type, SUPPORTED_MIME_TYPES
from app.ContentService import ContentService

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)  # Compress responses > 1KB

API_KEY = os.getenv("DOC_API_KEY", "my-secret-key")

service = ContentService()


@app.post("/parse")
async def parse_document(request: Request, x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    try:
        contents = await request.body()
        if not contents:
            raise HTTPException(status_code=400, detail="No content provided")
        content_type = request.headers.get("Content-Type")
        if not content_type:
            raise HTTPException(
                status_code=400,
                detail="No content type provided. Please add the Content-Type header",
            )
        if not is_supported_mime_type(content_type):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported content type: {content_type}",
            )
        filename = request.headers.get("filename")
        if not filename:
            filename = f"uploadedfile{SUPPORTED_MIME_TYPES[content_type]}"
        overwrite = request.headers.get("overwrite", "false").lower() == "true"
        result = service.process(contents, content_type, filename, overwrite)
        return JSONResponse(content=result.model_dump())
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, timeout_keep_alive=420)
