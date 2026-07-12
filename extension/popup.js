const translateSelectionButton = document.querySelector("#translate-selection");
const selectionResult = document.querySelector("#selection-result");

translateSelectionButton.addEventListener("click", async () => {
  let selectedText;

  try {
    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const response = await chrome.tabs.sendMessage(activeTab.id, {
      type: "GET_SELECTED_TEXT",
    });

    selectedText = response.selectedText;
  } catch (_error) {
    selectionResult.textContent = "Please select text on the webpage first.";
    selectionResult.hidden = false;
    return;
  }

  if (!selectedText) {
    selectionResult.textContent = "Please select text on the webpage first.";
    selectionResult.hidden = false;
    return;
  }

  selectionResult.textContent = "Processing text...";
  selectionResult.hidden = false;

  try {
    const response = await fetch("http://127.0.0.1:8000/process-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: selectedText }),
    });

    if (!response.ok) {
      throw new Error(`Backend request failed with status ${response.status}.`);
    }

    const result = await response.json();
    selectionResult.textContent = result.processed_text;
  } catch (_error) {
    selectionResult.textContent = "VitouLens local backend is not available.";
  }
});
