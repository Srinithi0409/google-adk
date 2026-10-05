let allData = JSON.parse(localStorage.getItem("uploadedData")) || [];
let fileName = localStorage.getItem("fileName");
let backendFilePath = localStorage.getItem("uploadedFilePath");
let analysisResult = JSON.parse(localStorage.getItem("aiAnalysis"));

// Set file name
document.getElementById("fileNameBox").innerText = fileName;

/****************************
  FIELDS TABLE
*****************************/
function renderFields(data) {
  const tableBody = document.getElementById("fieldsTableBody");
  if (!data.length) return;

  tableBody.innerHTML = "";
  const headers = Object.keys(data[0]);

  headers.forEach((h) => {
    const sample = data[0][h];
    let typeIcon = "Abc";
    if (!isNaN(sample)) typeIcon = "#";
    if (!isNaN(Date.parse(sample))) typeIcon = "📅";

    tableBody.innerHTML += `
      <tr>
        <td class="field-type-cell">${typeIcon}</td>
        <td>${h}</td>
      </tr>
    `;
  });
}

/****************************
  TABLE RENDERING
*****************************/
let startIndex = 0;

function renderTable() {
  const rowLimit = document.getElementById("rowLimit").value;
  let limit = rowLimit === "all" ? allData.length : parseInt(rowLimit);

  let rowsToShow = allData.slice(startIndex, startIndex + limit);

  if (!rowsToShow.length) {
    startIndex = 0;
    rowsToShow = allData.slice(0, limit);
  }

  const table = document.getElementById("dataTable");
  table.innerHTML = "";

  const headers = Object.keys(rowsToShow[0]);

  // Header
  let thead = "<tr>";
  headers.forEach((h) => (thead += `<th>${h}</th>`));
  thead += "</tr>";

  // Rows
  let tbody = "";
  rowsToShow.forEach((row) => {
    tbody += "<tr>";
    headers.forEach((h) => (tbody += `<td>${row[h]}</td>`));
    tbody += "</tr>";
  });

  table.innerHTML = thead + tbody;
}

/****************************
 NEXT BUTTON
*****************************/
document.getElementById("nextRowsBtn").onclick = () => {
  const rowLimit = document.getElementById("rowLimit").value;
  const limit = rowLimit === "all" ? allData.length : parseInt(rowLimit);

  startIndex += limit;

  if (startIndex >= allData.length) startIndex = 0;

  renderTable();
};

document.getElementById("rowLimit").onchange = () => {
  startIndex = 0;
  renderTable();
};

/****************************
 AI CHECKBOX ACTIVATION
*****************************/
document.getElementById("aiCheck").addEventListener("change", () => {
  if (!document.getElementById("aiCheck").checked) return;

  const suggestions = analysisResult.suggestions;
  const dropdown = document.getElementById("techniqueDropdown");

  dropdown.innerHTML = "";

  suggestions.forEach((s) => {
    dropdown.innerHTML += `<option value="${s.technique}">${s.technique}</option>`;
  });

  document.getElementById("aiOptions").style.display = "block";
});

/****************************
 APPLY CLEANING
*****************************/
document.getElementById("applyAI").onclick = async () => {
  const selected = document.getElementById("techniqueDropdown").value;
  const filePath = localStorage.getItem("uploadedFilePath");

  const response = await fetch("http://127.0.0.1:8000/clean", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_path: filePath,
      techniques: [selected],
    }),
  });

  const result = await response.json();

  // ⭐ get cleaned data (list of rows)
  const cleaned = result.cleaned_records;

  if (!cleaned || cleaned.length === 0) {
    alert("Cleaned data not received.");
    return;
  }

  // Update UI
  allData = cleaned;
  startIndex = 0;

  renderFields(allData);
  renderTable();
};

/****************************
 INITIAL LOAD
*****************************/
renderFields(allData);
renderTable();
