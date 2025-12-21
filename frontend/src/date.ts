export function formatDisplayDate(iso?: string | null | undefined): string {
  if (!iso) return ''
  // Attempt to parse the incoming ISO or datetime-local string
  const d = new Date(String(iso))
  if (isNaN(d.getTime())) return String(iso)
  const pad = (n: number) => n.toString().padStart(2, '0')
  const month = pad(d.getMonth() + 1)
  const day = pad(d.getDate())
  const year = d.getFullYear()
  let hours = d.getHours()
  const minutes = pad(d.getMinutes())
  const ampm = hours >= 12 ? 'PM' : 'AM'
  hours = hours % 12
  if (hours === 0) hours = 12
  const hh = pad(hours)
  return `${month}/${day}/${year}, ${hh}:${minutes} ${ampm}`
}

export default formatDisplayDate
