const BACKEND_URL = "http://127.0.0.1:8000/process-text";

chrome.runtime.onMessage.addListener(
  (message, _sender, sendResponse) => {
    if (message.type !== "TRANSLATE_TEXT") {
      return;
    }

    (async () => {
      try {
        const response = await fetch(BACKEND_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            text: message.text
          })
        });

        if (!response.ok) {
          let errorMessage =
            `Translation failed with status ${response.status}.`;

          try {
            const errorData = await response.json();

            if (errorData.detail) {
              errorMessage = errorData.detail;
            }
          } catch (_error) {
            // Keep the HTTP status message.
          }

          sendResponse({
            success: false,
            error: errorMessage
          });

          return;
        }

        const result = await response.json();

        sendResponse({
          success: true,
          processedText: result.processed_text
        });
      } catch (_error) {
        sendResponse({
          success: false,
          error: "VitouLens local backend is not available."
        });
      }
    })();

    return true;
  }
);