import { earnedCredits } from "./transcript.mjs";

const status = document.getElementById("document-status");
const list = document.getElementById("saved-documents");
const inputs = [
  [document.getElementById("cv-file"), "cv"],
  [document.getElementById("transcript-files"), "transcript"],
];

async function load() {
  return (await chrome.storage.local.get("documents")).documents || [];
}

async function render() {
  const documents = await load();
  list.replaceChildren();
  for (const doc of documents) {
    const item = document.createElement("div");
    item.className = "entry";
    const title = document.createElement("strong");
    title.textContent = (doc.kind === "cv" ? "CV: " : "Transcript: ") + doc.name;
    const detail = document.createElement("p");
    detail.className = "muted";
    detail.textContent = doc.summary;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remove";
    remove.setAttribute("aria-label", "Remove " + doc.name);
    remove.addEventListener("click", async () => {
      remove.disabled = true;
      try {
        await chrome.storage.local.set({ documents: (await load()).filter(saved => saved.id !== doc.id) });
        await render();
      } catch {
        status.textContent = "Could not remove this file.";
        remove.disabled = false;
      }
    });
    item.append(title, detail, remove);
    list.append(item);
  }
}

async function summarizeTranscript(bytes) {
  const pdfjs = await import("./vendor/pdfjs/pdf.min.mjs");
  pdfjs.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL("vendor/pdfjs/pdf.worker.min.mjs");
  const task = pdfjs.getDocument({
    data: bytes.slice(), isEvalSupported: false, enableXfa: false,
    useWasm: false, useSystemFonts: false, disableFontFace: true,
  });
  try {
    const pdf = await task.promise;
    if (pdf.numPages > 30) return "Enter the credit total manually for transcripts over 30 pages.";
    let text = "";
    for (let index = 1; index <= pdf.numPages; index++) {
      const page = await pdf.getPage(index);
      const content = await page.getTextContent();
      text += " " + content.items.map(item => item.str || "").join(" ");
      page.cleanup();
    }
    const credits = earnedCredits(text);
    if (!credits) return "No unambiguous earned-credit total found. Check the PDF and enter the value manually.";
    if (/\blafayette college\b/i.test(text)) {
      return "Overall earned credits: " + credits + " Lafayette course units (" + Number(credits) * 4 +
        " semester credit hours at Lafayette’s 4:1 equivalency). Verify which unit the portal asks for.";
    }
    return "Earned-credit total shown in the PDF: " + credits + ". Verify the unit before entering it.";
  } finally {
    await task.destroy();
  }
}

for (const [input, kind] of inputs) {
  input.addEventListener("change", async () => {
    const selected = Array.from(input.files);
    if (!selected.length) return;
    for (const [control] of inputs) control.disabled = true;
    status.textContent = "Reading selected PDFs on this device…";
    try {
      let documents = await load();
      for (const file of selected) {
        if (file.size > 4 * 1024 * 1024) throw new Error("PDFs must be 4 MB or smaller.");
        const bytes = new Uint8Array(await file.arrayBuffer());
        if (new TextDecoder().decode(bytes.subarray(0, 5)) !== "%PDF-")
          throw new Error("Choose a valid PDF.");
        let summary = "";
        if (kind === "transcript") {
          try { summary = await summarizeTranscript(bytes); }
          catch { summary = "Credit totals could not be read locally. Check the PDF and enter the total manually."; }
        }
        documents = documents.filter(doc => doc.kind !== kind || (kind === "transcript" && doc.name !== file.name));
        documents.push({ id: crypto.randomUUID(), kind, name: file.name, summary, data: bytes.toBase64() });
      }
      await chrome.storage.local.set({ documents });
      await render();
      status.textContent = "PDFs saved locally.";
    } catch (error) {
      status.textContent = "PDFs could not be saved. Check the file format, size and browser storage space. " + error.message;
    } finally {
      input.value = "";
      for (const [control] of inputs) control.disabled = false;
    }
  });
}
render();
