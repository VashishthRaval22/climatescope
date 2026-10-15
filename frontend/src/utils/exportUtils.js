function downloadCsv(filename, headers, rows) {
  const escape = (value) => {
    const text = value == null ? '' : String(value);
    return `"${text.replace(/"/g, '""')}"`;
  };
  const csv = [headers, ...rows].map((row) => row.map(escape).join(',')).join('\r\n');
  const blob = new Blob(['\uFEFF', csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = filename; anchor.click();
  URL.revokeObjectURL(url);
}

async function exportPdf(title, subtitle, headers, rows) {
  const { default: jsPDF } = await import('jspdf');
  const { default: autoTable } = await import('jspdf-autotable');
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' });
  doc.setFillColor(194, 65, 12); doc.rect(0, 0, doc.internal.pageSize.getWidth(), 58, 'F');
  doc.setTextColor(255, 255, 255); doc.setFontSize(18); doc.text('ClimateScope', 40, 27);
  doc.setFontSize(10); doc.text('Executive Climate Hazard Report', 40, 44);
  doc.setTextColor(23, 32, 51); doc.setFontSize(15); doc.text(title, 40, 86);
  doc.setFontSize(9); doc.setTextColor(102, 112, 133); doc.text(subtitle, 40, 103);
  autoTable(doc, { startY: 122, head: [headers], body: rows, theme: 'grid', styles: { fontSize: 8, cellPadding: 5 }, headStyles: { fillColor: [249, 250, 251], textColor: [52, 64, 84] }, margin: { left: 40, right: 40 } });
  const footer = `ClimateScope · ERA5-Land daily maximum temperature · Baseline 1991–2020 · P90/P95 thresholds · Generated ${new Date().toLocaleString()}`;
  const pages = doc.getNumberOfPages();
  for (let page = 1; page <= pages; page++) { doc.setPage(page); doc.setFontSize(8); doc.setTextColor(102, 112, 133); doc.text(footer, 40, doc.internal.pageSize.getHeight() - 20); }
  doc.save('climatescope-report.pdf');
}


export { downloadCsv, exportPdf };
