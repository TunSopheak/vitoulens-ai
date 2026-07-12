const translateSelectionButton =
  document.querySelector("#translate-selection");

const translatePageButton =
  document.querySelector("#translate-page");

const stopTranslationButton =
  document.querySelector("#stop-translation");

const selectionResult =
  document.querySelector("#selection-result");


function showStatus(message) {
  selectionResult.textContent = message;
  selectionResult.hidden = false;
}


async function getActiveTab() {
  const [activeTab] = await chrome.tabs.query({
    active: true,
    currentWindow: true
  });

  return activeTab;
}


async function sendPageCommand(type) {
  try {
    const activeTab = await getActiveTab();

    return await chrome.tabs.sendMessage(
      activeTab.id,
      { type }
    );
  } catch (_error) {
    return null;
  }
}


translateSelectionButton.addEventListener(
  "click",
  async () => {
    const result = await sendPageCommand(
      "TRANSLATE_SELECTED_BLOCKS"
    );

    if (!result?.started) {
      showStatus(
        result?.message ??
          "Please select text on the webpage first."
      );

      return;
    }

    showStatus(
      `Translation started for ${result.blockCount} selected block(s).`
    );
  }
);


translatePageButton.addEventListener(
  "click",
  async () => {
    const result = await sendPageCommand(
      "TRANSLATE_CURRENT_PAGE"
    );

    if (!result?.started) {
      showStatus(
        result?.message ??
          "Could not start page translation."
      );

      return;
    }

    showStatus(
      `Page translation started for ${result.blockCount} block(s).`
    );
  }
);


stopTranslationButton.addEventListener(
  "click",
  async () => {
    const result = await sendPageCommand(
      "STOP_AND_RESTORE"
    );

    if (!result?.success) {
      showStatus(
        "Could not restore the original webpage."
      );

      return;
    }

    showStatus(
      `Restored ${result.restoredCount} original block(s).`
    );
  }
);