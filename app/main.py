import os

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .docling_conversion import DoclingConversionResult, DoclingConverter

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)  # Compress responses > 1KB

API_KEY = os.getenv("DOC_API_KEY", "my-secret-key")


def make_res(result: DoclingConversionResult):
    """
    Create a response model from the conversion result.
    """

    return {
        "started_at": result.started_at,
        "seconds_taken": result.seconds_taken,
        "content_type": result.content_type,
        "content_hash": result.content_hash,
        "chunks": result.chunks,
        "filename": result.filename,
        "attachments": (
            [make_res(attachment) for attachment in result.attachments]
            if result.attachments
            else None
        ),
    }


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
        filename = request.headers.get("filename", "uploaded")
        result = DoclingConverter().convert(content_type, contents, filename)
        result_doc = make_res(result)
        return JSONResponse(content=result_doc)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, timeout_keep_alive=360)
