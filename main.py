import uvicorn
import os


def main() -> None:
    port = int(os.getenv("PORT", "80"))
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=port,
        loop="api.uvicorn_loop:selector_loop_factory",
    )


if __name__ == "__main__":
    main()
