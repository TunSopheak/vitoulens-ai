const translateSelectionButton = document.querySelector("#translate-selection");
const selectionResult = document.querySelector("#selection-result");

translateSelectionButton.addEventListener("click", async () => {
  try {
    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const response = await chrome.tabs.sendMessage(activeTab.id, {
      type: "GET_SELECTED_TEXT",
    });

    selectionResult.textContent =
      response.selectedText || "Please select text on the webpage first.";
  } catch (_error) {
    selectionResult.textContent = "Please select text on the webpage first.";
  }

  selectionResult.hidden = false;
});
