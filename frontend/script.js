// Excel button → open picker
document.getElementById("excel-btn").onclick = () => {
  document.getElementById("excel-file-input").click();
};

// Text/CSV button → open picker
document.getElementById("text-btn").onclick = () => {
  document.getElementById("text-file-input").click();
};

/**********************
 📌 UPLOAD EXCEL
***********************/
document
  .getElementById("excel-file-input")
  .addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Save client-side preview for page2
    const reader = new FileReader();
    reader.onload = function (event) {
      const data = new Uint8Array(event.target.result);
      const workbook = XLSX.read(data, { type: "array" });

      const sheetName = workbook.SheetNames[0];
      const sheet = workbook.Sheets[sheetName];
      const parsedRows = XLSX.utils.sheet_to_json(sheet);

      localStorage.setItem("uploadedData", JSON.stringify(parsedRows));
      localStorage.setItem("fileName", file.name);
    };
    reader.readAsArrayBuffer(file);

    // ---------- Send file to backend ----------
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("http://127.0.0.1:8000/upload", {
      method: "POST",
      body: formData,
    });

    const result = await res.json();
    localStorage.setItem("uploadedFilePath", result.file_path);
    localStorage.setItem("aiAnalysis", JSON.stringify(result.recommendations));

    // Next page
    window.location.href = "i.html";
  });

/**********************
 📌 UPLOAD CSV
***********************/
document
  .getElementById("text-file-input")
  .addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function (event) {
      const csvText = event.target.result;
      const rows = csvText.split("\n").map((row) => row.split(","));
      const headers = rows[0];

      const parsedRows = rows.slice(1).map((row) => {
        const obj = {};
        headers.forEach(
          (h, i) => (obj[h.trim()] = row[i] ? row[i].trim() : "")
        );
        return obj;
      });

      localStorage.setItem("uploadedData", JSON.stringify(parsedRows));
      localStorage.setItem("fileName", file.name);
    };
    reader.readAsText(file);

    // ---------- Send file to backend ----------
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("http://127.0.0.1:8000/upload", {
      method: "POST",
      body: formData,
    });

    const result = await res.json();
    localStorage.setItem("uploadedFilePath", result.file_path);
    localStorage.setItem("aiAnalysis", JSON.stringify(result.recommendations));

    window.location.href = "i.html";
  });
