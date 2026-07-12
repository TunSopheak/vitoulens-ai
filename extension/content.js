console.log("VitouLens AI content script loaded.");

const BLOCK_SELECTOR = [
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "p",
  "li",
  "blockquote",
  "td",
  "th"
].join(",");

const EXCLUDED_SELECTOR = [
  "nav",
  "header",
  "footer",
  "aside",
  "script",
  "style",
  "noscript",
  "pre",
  "button",
  "input",
  "textarea",
  "select",
  "[contenteditable='true']",
  ".vitoulens-page-controller",
  "[data-vitoulens-generated='true']"
].join(",");

const originalBlocks = new Map();

let translationSession = 0;
let translationRunning = false;
let controller = null;
let controllerStatus = null;
let controllerButton = null;


function getContentRoot() {
  const preferredRoots = [
    document.querySelector("article"),
    document.querySelector("[role='main']"),
    document.querySelector("main")
  ];

  for (const root of preferredRoots) {
    if (
      root &&
      root.innerText &&
      root.innerText.trim().length >= 100
    ) {
      return root;
    }
  }

  return document.body;
}


function isCandidateBlock(element) {
  if (!(element instanceof HTMLElement)) {
    return false;
  }

  if (element.closest(EXCLUDED_SELECTOR)) {
    return false;
  }

  if (element.classList.contains("vitoulens-translated-block")) {
    return false;
  }

  const text = element.innerText?.trim() ?? "";

  if (text.length < 3 || text.length > 5000) {
    return false;
  }

  if (!/[A-Za-z]/.test(text)) {
    return false;
  }

  const nestedBlocks = Array.from(
    element.querySelectorAll(BLOCK_SELECTOR)
  );

  const containsReadableNestedBlock = nestedBlocks.some(
    (child) =>
      child !== element &&
      (child.innerText?.trim().length ?? 0) >= 3
  );

  return !containsReadableNestedBlock;
}


function getCandidateBlocks(root = getContentRoot()) {
  return Array.from(
    root.querySelectorAll(BLOCK_SELECTOR)
  ).filter(isCandidateBlock);
}


function getSelectedBlocks() {
  const selection = window.getSelection();

  if (
    !selection ||
    selection.isCollapsed ||
    !selection.toString().trim() ||
    !selection.rangeCount
  ) {
    return [];
  }

  const range = selection.getRangeAt(0);

  return getCandidateBlocks(document.body).filter((element) => {
    try {
      return range.intersectsNode(element);
    } catch (_error) {
      return false;
    }
  });
}


function saveOriginalBlock(element) {
  if (originalBlocks.has(element)) {
    return;
  }

  originalBlocks.set(element, {
    innerHTML: element.innerHTML,
    lang: element.getAttribute("lang")
  });
}


function createController() {
  if (controller && document.contains(controller)) {
    return;
  }

  controller = document.createElement("section");
  controller.className = "vitoulens-page-controller";
  controller.setAttribute("data-vitoulens-generated", "true");

  const brand = document.createElement("strong");
  brand.className = "vitoulens-controller-brand";
  brand.textContent = "VitouLens AI";

  controllerStatus = document.createElement("span");
  controllerStatus.className = "vitoulens-controller-status";
  controllerStatus.textContent = "Preparing translation...";

  controllerButton = document.createElement("button");
  controllerButton.type = "button";
  controllerButton.className = "vitoulens-controller-stop";
  controllerButton.textContent = "Stop & Restore English";

  controllerButton.addEventListener("click", () => {
    restoreOriginalPage();
  });

  controller.append(
    brand,
    controllerStatus,
    controllerButton
  );

  document.documentElement.appendChild(controller);
}


function updateController(message, completed = false) {
  createController();

  controllerStatus.textContent = message;
  controllerButton.textContent = completed
    ? "Restore English"
    : "Stop & Restore English";
}


function removeController() {
  controller?.remove();

  controller = null;
  controllerStatus = null;
  controllerButton = null;
}


function restoreOriginalPage() {
  translationSession += 1;
  translationRunning = false;

  let restoredCount = 0;

  for (const [element, original] of originalBlocks) {
    if (!document.contains(element)) {
      continue;
    }

    element.innerHTML = original.innerHTML;

    if (original.lang === null) {
      element.removeAttribute("lang");
    } else {
      element.setAttribute("lang", original.lang);
    }

    element.classList.remove(
      "vitoulens-translated-block",
      "vitoulens-translating-block"
    );

    element.removeAttribute("aria-busy");

    restoredCount += 1;
  }

  originalBlocks.clear();
  removeController();

  return restoredCount;
}


async function runTranslation(blocks) {
  if (translationRunning) {
    return;
  }

  translationRunning = true;

  const currentSession = ++translationSession;
  const total = blocks.length;

  createController();
  updateController(`Translating 0 of ${total} blocks...`);

  let translatedCount = 0;

  for (const block of blocks) {
    if (currentSession !== translationSession) {
      return;
    }

    const sourceText = block.innerText?.trim() ?? "";

    if (!sourceText) {
      continue;
    }

    block.classList.add("vitoulens-translating-block");
    block.setAttribute("aria-busy", "true");

    let result;

    try {
      result = await chrome.runtime.sendMessage({
        type: "TRANSLATE_TEXT",
        text: sourceText
      });
    } catch (_error) {
      result = {
        success: false,
        error: "VitouLens translation service failed."
      };
    }

    if (currentSession !== translationSession) {
      return;
    }

    block.classList.remove("vitoulens-translating-block");
    block.removeAttribute("aria-busy");

    if (!result?.success) {
      translationRunning = false;

      updateController(
        result?.error ?? "Translation failed.",
        true
      );

      return;
    }

    saveOriginalBlock(block);

    block.textContent = result.processedText;
    block.lang = "km";
    block.classList.add("vitoulens-translated-block");

    translatedCount += 1;

    updateController(
      `Translating ${translatedCount} of ${total} blocks...`
    );
  }

  translationRunning = false;

  updateController(
    `Translated ${translatedCount} blocks.`,
    true
  );
}


function startTranslation(blocks) {
  if (translationRunning) {
    return {
      started: false,
      message: "Translation is already running."
    };
  }

  if (!blocks.length) {
    return {
      started: false,
      message: "No English learning content was found."
    };
  }

  runTranslation(blocks).catch(() => {
    translationRunning = false;

    updateController(
      "VitouLens translation failed.",
      true
    );
  });

  return {
    started: true,
    blockCount: blocks.length
  };
}


chrome.runtime.onMessage.addListener(
  (message, _sender, sendResponse) => {
    if (message.type === "TRANSLATE_SELECTED_BLOCKS") {
      const blocks = getSelectedBlocks();

      if (!blocks.length) {
        sendResponse({
          started: false,
          message: "Please select text on the webpage first."
        });

        return;
      }

      sendResponse(startTranslation(blocks));
      return;
    }

    if (message.type === "TRANSLATE_CURRENT_PAGE") {
      const blocks = getCandidateBlocks();

      sendResponse(startTranslation(blocks));
      return;
    }

    if (message.type === "STOP_AND_RESTORE") {
      const restoredCount = restoreOriginalPage();

      sendResponse({
        success: true,
        restoredCount
      });
    }
  }
);