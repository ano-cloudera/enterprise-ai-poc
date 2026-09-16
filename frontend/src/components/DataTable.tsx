import { formatBusinessLabel, formatBusinessValue } from '../lib/businessPresentation'

export function DataTable({ columns, rows, metric }: { columns: string[]; rows: Record<string, unknown>[]; metric?: string }) {
  if (!columns.length || !Array.isArray(rows) || !rows.length) {
    return <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">No structured table data is available.</div>
  }
  return (
    <div className="mt-4 max-h-72 overflow-auto rounded-xl border border-slate-200">
      <table className="min-w-full whitespace-nowrap text-left text-xs">
        <thead className="sticky top-0 bg-slate-50 text-slate-500"><tr>{columns.map(column => <th key={column} className="px-3 py-2.5 font-extrabold">{formatBusinessLabel(column)}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => <tr key={index} className="border-t border-slate-100 bg-white">{columns.map(column => <td key={column} className="px-3 py-2.5 text-slate-700">{formatBusinessValue(column, row[column], metric)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}
