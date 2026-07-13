console.log("VitouLens AI content script loaded.");

const {
  BLOCK_SELECTOR,
  EXCLUDED_SELECTOR,
  MIN_BLOCK_TEXT_LENGTH,
  MAX_PAGE_BLOCKS,
  normalizeBlockText,
  isCandidateText,
  buildBatchItems,
  mapBatchTranslations,
} = globalThis.VitouLensContentLogic;

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
    document.querySelector("main"),
  ];

  for (const root of preferredRoots) {
    const rootText = normalizeBlockText(
      root?.innerText
    );

    if (root && rootText.length >= 100) {
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

  if (
    element.classList.contains(
      "vitoulens-translated-block"
    )
  ) {
    return false;
  }

  const text = normalizeBlockText(
    element.innerText
  );

  if (!isCandidateText(text)) {
    return false;
  }

  const nestedBlocks = Array.from(
    element.querySelectorAll(BLOCK_SELECTOR)
  );

  const containsReadableNestedBlock = (
    nestedBlocks.some((child) => (
      normalizeBlockText(
        child.innerText
      ).length >= MIN_BLOCK_TEXT_LENGTH
    ))
  );

  return !containsReadableNestedBlock;
}


function getCandidateBlocks(
  root = getContentRoot(),
) {
  if (!root) {
    return [];
  }

  return Array.from(
    root.querySelectorAll(BLOCK_SELECTOR)
  ).filter(isCandidateBlock);
}


function createPageTranslationPlan() {
  const candidateBlocks = getCandidateBlocks();

  const blocks = candidateBlocks.slice(
    0,
    MAX_PAGE_BLOCKS,
  );

  const items = buildBatchItems(
    blocks.map((block) => (
      normalizeBlockText(block.innerText)
    ))
  );

  return {
    blocks,
    items,
    candidateCount: candidateBlocks.length,
    truncated: (
      candidateBlocks.length > blocks.length
    ),
  };
}


function saveOriginalBlock(element) {
  if (originalBlocks.has(element)) {
    return;
  }

  originalBlocks.set(element, {
    innerHTML: element.innerHTML,
    lang: element.getAttribute("lang"),
  });
}


function saveOriginalBlocks(blocks) {
  for (const block of blocks) {
    saveOriginalBlock(block);
  }
}


function markBlocksBusy(blocks) {
  for (const block of blocks) {
    block.classList.add(
      "vitoulens-translating-block"
    );

    block.setAttribute(
      "aria-busy",
      "true",
    );
  }
}


function clearBlocksBusy(blocks) {
  for (const block of blocks) {
    block.classList.remove(
      "vitoulens-translating-block"
    );

    block.removeAttribute("aria-busy");
  }
}


function applyBlockTranslation(
  block,
  translation,
) {
  const translatedText = normalizeBlockText(
    translation
  );

  if (
    !(block instanceof HTMLElement)
    || !translatedText
  ) {
    throw new Error(
      "Translated page block is invalid."
    );
  }

  saveOriginalBlock(block);

  block.textContent = translatedText;
  block.setAttribute("lang", "km");

  block.classList.add(
    "vitoulens-translated-block"
  );

  block.classList.remove(
    "vitoulens-translating-block"
  );

  block.removeAttribute("aria-busy");
}


function createController() {
  if (
    controller
    && document.contains(controller)
  ) {
    return;
  }

  controller = document.createElement(
    "section"
  );

  controller.className = (
    "vitoulens-page-controller"
  );

  controller.setAttribute(
    "data-vitoulens-generated",
    "true",
  );

  const brand = document.createElement(
    "strong"
  );

  brand.className = (
    "vitoulens-controller-brand"
  );

  brand.textContent = "VitouLens AI";

  controllerStatus = document.createElement(
    "span"
  );

  controllerStatus.className = (
    "vitoulens-controller-status"
  );

  controllerButton = document.createElement(
    "button"
  );

  controllerButton.type = "button";

  controllerButton.className = (
    "vitoulens-controller-stop"
  );

  controllerButton.addEventListener(
    "click",
    () => {
      restoreOriginalPage();
    }
  );

  controller.append(
    brand,
    controllerStatus,
    controllerButton,
  );

  document.documentElement.appendChild(
    controller
  );
}


function updateController(
  message,
  completed = false,
) {
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
      element.setAttribute(
        "lang",
        original.lang,
      );
    }

    element.classList.remove(
      "vitoulens-translated-block",
      "vitoulens-translating-block",
    );

    element.removeAttribute("aria-busy");

    restoredCount += 1;
  }

  originalBlocks.clear();
  removeController();

  return restoredCount;
}


function yieldToPage() {
  return new Promise((resolve) => {
    setTimeout(resolve, 0);
  });
}


async function runPageTranslation(
  plan,
  mode,
) {
  translationRunning = true;

  const currentSession = (
    ++translationSession
  );

  const {
    blocks,
    items,
    candidateCount,
    truncated,
  } = plan;

  const total = blocks.length;

  saveOriginalBlocks(blocks);
  markBlocksBusy(blocks);

  updateController(
    `Translating 0 of ${total} blocks...`
  );

  let result;

  try {
    result = await chrome.runtime.sendMessage({
      type: "TRANSLATE_BATCH",
      items,
      mode,
    });
  } catch (_error) {
    result = {
      ok: false,
      error: (
        "VitouLens translation service failed."
      ),
    };
  }

  if (currentSession !== translationSession) {
    return;
  }

  if (!result?.ok) {
    clearBlocksBusy(blocks);
    originalBlocks.clear();

    translationRunning = false;

    updateController(
      result?.error ?? "Translation failed.",
      true,
    );

    return;
  }

  let translations;

  try {
    translations = mapBatchTranslations(
      items,
      result.results,
    );
  } catch (_error) {
    restoreOriginalPage();

    updateController(
      (
        "VitouLens received an invalid "
        + "batch translation response."
      ),
      true,
    );

    return;
  }

  let translatedCount = 0;

  for (
    let index = 0;
    index < blocks.length;
    index += 1
  ) {
    if (
      currentSession !== translationSession
    ) {
      return;
    }

    applyBlockTranslation(
      blocks[index],
      translations[index].translation,
    );

    translatedCount += 1;

    updateController(
      (
        `Translating ${translatedCount} `
        + `of ${total} blocks...`
      )
    );

    await yieldToPage();
  }

  if (currentSession !== translationSession) {
    return;
  }

  translationRunning = false;

  const completionMessage = truncated
    ? (
      `Translated ${translatedCount} of `
      + `${candidateCount} detected blocks.`
    )
    : `Translated ${translatedCount} blocks.`;

  updateController(
    completionMessage,
    true,
  );
}


function startPageTranslation(mode) {
  if (translationRunning) {
    return {
      started: false,
      message: (
        "Page translation is already running."
      ),
    };
  }

  const plan = createPageTranslationPlan();

  if (!plan.blocks.length) {
    return {
      started: false,
      message: (
        "No English learning content was found."
      ),
    };
  }

  runPageTranslation(
    plan,
    mode,
  ).catch(() => {
    restoreOriginalPage();

    updateController(
      "VitouLens page translation failed.",
      true,
    );
  });

  return {
    started: true,
    blockCount: plan.blocks.length,
    candidateCount: plan.candidateCount,
    truncated: plan.truncated,
  };
}


chrome.runtime.onMessage.addListener(
  (message, _sender, sendResponse) => {
    if (message?.type === "GET_SELECTED_TEXT") {
      const selectedText = (
        window.getSelection()
          ?.toString()
          .trim()
        ?? ""
      );

      sendResponse({
        selectedText,
      });

      return;
    }

    if (
      message?.type
      === "TRANSLATE_CURRENT_PAGE"
    ) {
      sendResponse(
        startPageTranslation(message.mode)
      );

      return;
    }

    if (
      message?.type
      === "RESTORE_ORIGINAL_PAGE"
    ) {
      sendResponse({
        success: true,
        restoredCount: restoreOriginalPage(),
      });
    }
  }
);
