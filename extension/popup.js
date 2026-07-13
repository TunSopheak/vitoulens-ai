const {
  BASIC_MODE,
  SMART_MODE,
  normalizeStoredMode,
  buildRequestPayload,
  extractTranslation,
  getHttpErrorMessage,
  getBackendUnavailableMessage,
  getInvalidBackendResponseMessage,
} = globalThis.VitouLensPopupLogic;

const translateSelectionButton = (
  document.querySelector(
    "#translate-selection"
  )
);

const translatePageButton = (
  document.querySelector(
    "#translate-page"
  )
);

const selectionResult = document.querySelector(
  "#selection-result"
);

const modeInputs = [
  ...document.querySelectorAll(
    'input[name="translation-mode"]'
  ),
];

let selectedMode = BASIC_MODE;


function showResult(message) {
  selectionResult.textContent = message;
  selectionResult.hidden = false;
}


function applySelectedMode(mode) {
  selectedMode = normalizeStoredMode(mode);

  const selectedInput = modeInputs.find(
    (input) => input.value === selectedMode
  );

  if (selectedInput) {
    selectedInput.checked = true;
  }
}


async function loadSelectedMode() {
  try {
    const stored = await chrome.storage.local.get(
      "translationMode"
    );

    applySelectedMode(
      stored.translationMode
    );
  } catch (_error) {
    applySelectedMode(BASIC_MODE);
  }
}


async function getActiveTab() {
  const [activeTab] = await chrome.tabs.query({
    active: true,
    currentWindow: true,
  });

  if (
    !activeTab
    || typeof activeTab.id !== "number"
  ) {
    throw new Error(
      "Active tab is unavailable."
    );
  }

  return activeTab;
}


for (const input of modeInputs) {
  input.addEventListener(
    "change",
    async () => {
      if (!input.checked) {
        return;
      }

      applySelectedMode(input.value);

      try {
        await chrome.storage.local.set({
          translationMode: selectedMode,
        });
      } catch (_error) {
        // Keep the in-memory selection.
      }
    }
  );
}


translateSelectionButton.addEventListener(
  "click",
  async () => {
    let selectedText;

    try {
      const activeTab = await getActiveTab();

      const response = (
        await chrome.tabs.sendMessage(
          activeTab.id,
          {
            type: "GET_SELECTED_TEXT",
          },
        )
      );

      selectedText = response.selectedText;
    } catch (_error) {
      showResult(
        "Please select text on the webpage first."
      );

      return;
    }

    if (!selectedText) {
      showResult(
        "Please select text on the webpage first."
      );

      return;
    }

    showResult("Processing text...");

    let response;

    try {
      response = await fetch(
        "http://127.0.0.1:8000/process-text",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(
            buildRequestPayload(
              selectedText,
              selectedMode,
            )
          ),
        }
      );
    } catch (_error) {
      showResult(
        getBackendUnavailableMessage()
      );

      return;
    }

    if (!response.ok) {
      showResult(
        getHttpErrorMessage(
          selectedMode,
          response.status,
        )
      );

      return;
    }

    try {
      const result = await response.json();

      showResult(
        extractTranslation(
          result,
          selectedMode,
        )
      );
    } catch (_error) {
      showResult(
        getInvalidBackendResponseMessage()
      );
    }
  }
);


translatePageButton.addEventListener(
  "click",
  async () => {
    showResult(
      "Preparing current page translation..."
    );

    let response;

    try {
      const activeTab = await getActiveTab();

      response = await chrome.tabs.sendMessage(
        activeTab.id,
        {
          type: "TRANSLATE_CURRENT_PAGE",
          mode: selectedMode,
        },
      );
    } catch (_error) {
      showResult(
        "VitouLens is not available on this page."
      );

      return;
    }

    if (!response?.started) {
      showResult(
        response?.message
        ?? "Page translation could not start."
      );

      return;
    }

    const modeLabel = (
      selectedMode === SMART_MODE
        ? "Smart"
        : "Basic"
    );

    const scopeMessage = response.truncated
      ? (
        `${response.blockCount} of `
        + `${response.candidateCount} detected blocks`
      )
      : `${response.blockCount} page blocks`;

    showResult(
      (
        `Started ${modeLabel} Mode for `
        + `${scopeMessage}. `
        + "Progress is shown on the webpage."
      )
    );
  }
);


loadSelectedMode();
