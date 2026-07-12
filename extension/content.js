console.log("VitouLens AI content script loaded.");

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "GET_SELECTED_TEXT") {
    const selectedText = window.getSelection().toString().trim();
    sendResponse({ selectedText });
  }
});
