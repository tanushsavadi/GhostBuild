import top from './top.json'
import phraseBook from './phrases.json'
import checkedFile from './checked.json'
import { cardForWord, CREDIT, type Card } from './matcher'

// Review page: compare each card with its reference video and mark it right or
// wrong. Marks live in this browser (localStorage) and export as the "checked"
// map for g2/src/checked.json.

const KEY = 'sign-review-v1'
type Marks = Record<string, string> // word -> "ok" | "wrong: note"

function load(): Marks {
  try {
    return { ...(checkedFile.checked as Marks), ...JSON.parse(localStorage.getItem(KEY) ?? '{}') }
  } catch {
    return { ...(checkedFile.checked as Marks) }
  }
}

function save(): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(marks))
  } catch {
    // Private mode or blocked storage: marks still work until the page closes.
  }
}

const marks = load()

function phraseWords(): string[] {
  const words = new Set<string>()
  for (const p of phraseBook.phrases) for (const step of p.asl) if (typeof step === 'string') words.add(step)
  return [...words]
}

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T
const listSel = $<HTMLSelectElement>('list')
const filterSel = $<HTMLSelectElement>('filter')
const container = $<HTMLDivElement>('signs')
$<HTMLParagraphElement>('credit').textContent = CREDIT

function el(tag: string, text = '', attrs: Record<string, string> = {}): HTMLElement {
  const e = document.createElement(tag)
  e.textContent = text
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v)
  return e
}

function row(word: string, rank: number, card: Card): HTMLElement {
  const mark = marks[word] ?? ''
  const box = el('div', '', { class: `sign ${mark === 'ok' ? 'ok' : mark ? 'wrong' : ''}` })
  box.append(card.handshape ? el('img', '', { src: `/handshapes/${card.handshape}_bold.png`, alt: `${card.handshape} handshape` }) : el('div'))

  const body = el('div')
  const title = el('h2', card.title)
  title.append(el('span', `  #${rank} · "${word}"`, { class: 'rank' }))
  body.append(title, el('div', `${card.how[0]} / ${card.how[1]}`, { class: 'lines' }), el('div', card.label, { class: 'label' }))

  if (card.detail) {
    const d = el('details')
    d.append(el('summary', 'Full description'), el('p', card.detail.text))
    const src = el('a', 'Wiktionary', { href: card.detail.url, target: '_blank', rel: 'noopener' })
    const credit = el('small', 'Adapted from ')
    credit.append(src, ', CC BY-SA 4.0')
    d.append(credit)
    body.append(d)
  }
  if (card.video) body.append(el('a', '▶ Reference video (ASL-LEX)', { href: card.video, target: '_blank', rel: 'noopener' }))

  const verdict = el('div', '', { class: 'verdict' })
  const right = el('button', '✓ Right', { class: 'right' })
  const wrong = el('button', '✗ Wrong', { class: 'wrong' })
  const note = el('input', '', { placeholder: 'What is wrong? (optional)' }) as HTMLInputElement
  note.value = mark.startsWith('wrong:') ? mark.slice(6).trim() : ''
  right.onclick = () => { marks[word] = 'ok'; save(); render() }
  wrong.onclick = () => { marks[word] = `wrong: ${note.value}`; save(); render() }
  note.onchange = () => { if (marks[word]?.startsWith('wrong')) { marks[word] = `wrong: ${note.value}`; save() } }
  verdict.append(right, wrong, note)
  body.append(verdict)

  box.append(body)
  return box
}

function render(): void {
  const words = listSel.value === 'phrases' ? phraseWords() : (top as string[])
  const filter = filterSel.value
  container.replaceChildren()
  let done = 0
  words.forEach((word, i) => {
    const card = cardForWord(word)
    if (!card) return
    const mark = marks[word]
    if (mark) done++
    if (filter === 'todo' && mark) return
    if (filter === 'wrong' && !mark?.startsWith('wrong')) return
    container.append(row(word, i + 1, card))
  })
  $<HTMLSpanElement>('count').textContent = `${done}/${words.length} marked`
}

$<HTMLButtonElement>('export').onclick = async () => {
  const out = $<HTMLTextAreaElement>('out')
  out.value = JSON.stringify({ checked: marks }, null, 2)
  out.hidden = false
  out.select()
  try {
    await navigator.clipboard.writeText(out.value)
    $<HTMLButtonElement>('export').textContent = 'Copied'
  } catch {
    $<HTMLButtonElement>('export').textContent = 'Copy the text below'
  }
}

listSel.onchange = render
filterSel.onchange = render
render()
