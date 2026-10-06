const A4_WIDTH_MM = 210
const A4_HEIGHT_MM = 297

export function conversationPdfFilename(title: string): string {
  const safeTitle = title.replace(/[^\w\s-]+/g, '').trim().replace(/\s+/g, '-').slice(0, 48) || 'conversation'
  const stamp = new Date().toISOString().slice(0, 10)
  return `tempo-scan-${safeTitle}-${stamp}.pdf`
}

function prepareExportClone(source: HTMLElement): HTMLElement {
  const clone = source.cloneNode(true) as HTMLElement
  clone.style.position = 'fixed'
  clone.style.left = '-10000px'
  clone.style.top = '0'
  clone.style.zIndex = '-1'
  clone.style.width = `${source.scrollWidth}px`
  clone.style.maxHeight = 'none'
  clone.style.height = 'auto'
  clone.style.overflow = 'visible'
  clone.style.background = '#ffffff'
  clone.querySelectorAll<HTMLElement>('[class*="overflow"]').forEach(node => {
    node.style.overflow = 'visible'
    node.style.maxHeight = 'none'
  })
  document.body.appendChild(clone)
  return clone
}

export async function downloadConversationPdf(source: HTMLElement, title: string): Promise<void> {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([import('html2canvas'), import('jspdf')])

  const clone = prepareExportClone(source)
  try {
    const canvas = await html2canvas(clone, {
      scale: 2,
      backgroundColor: '#ffffff',
      useCORS: true,
      logging: false,
      width: clone.scrollWidth,
      height: clone.scrollHeight,
      windowWidth: clone.scrollWidth,
      windowHeight: clone.scrollHeight,
    })

    const pdf = new jsPDF({ orientation: 'p', unit: 'mm', format: 'a4' })
    const imgWidthMm = A4_WIDTH_MM
    const imgHeightMm = (canvas.height * imgWidthMm) / canvas.width
    const imgData = canvas.toDataURL('image/png')

    let heightLeftMm = imgHeightMm
    let positionMm = 0

    pdf.addImage(imgData, 'PNG', 0, positionMm, imgWidthMm, imgHeightMm)
    heightLeftMm -= A4_HEIGHT_MM

    while (heightLeftMm > 0) {
      positionMm = heightLeftMm - imgHeightMm
      pdf.addPage()
      pdf.addImage(imgData, 'PNG', 0, positionMm, imgWidthMm, imgHeightMm)
      heightLeftMm -= A4_HEIGHT_MM
    }

    pdf.save(conversationPdfFilename(title))
  } finally {
    clone.remove()
  }
}
