import { colors } from '../api/client'
import type { WorkItemCreate } from '../api/client'

export interface WorkItemDraft {
  title: string
  urgency: string
  importance: string
  color: string
  dueOn: string
  background: string
  goal: string
}

export const emptyDraft: WorkItemDraft = {
  title: '', urgency: '', importance: '', color: '', dueOn: '', background: '', goal: '',
}

export const colorLabels = {
  gray: '灰色', blue: '蓝色', green: '绿色', yellow: '黄色',
  orange: '橙色', red: '红色', purple: '紫色',
}

function toPayload(draft: WorkItemDraft): WorkItemCreate {
  return {
    title: draft.title.trim(),
    urgency: draft.urgency === '' ? null : draft.urgency === 'true',
    importance: draft.importance === '' ? null : draft.importance === 'true',
    color_key: colors.find(color => color === draft.color) ?? null,
    due_on: draft.dueOn || null,
    background: draft.background || null,
    goal: draft.goal || null,
  }
}

interface Props {
  draft: WorkItemDraft
  onChange: (draft: WorkItemDraft) => void
  onSubmit: (payload: WorkItemCreate) => void
  busy: boolean
  error: string | null
  created: boolean
}

export function WorkItemForm({ draft, onChange, onSubmit, busy, error, created }: Props) {
  const update = (key: keyof WorkItemDraft, value: string) => onChange({ ...draft, [key]: value })

  return (
    <section className="card" aria-labelledby="create-title">
      <h2 id="create-title">记录新的工作项</h2>
      <p className="muted">先写下来，再逐步明确优先级。任一优先级未设置时，工作项归为待分类。</p>
      <form onSubmit={event => {
        event.preventDefault()
        if (draft.title.trim()) onSubmit(toPayload(draft))
      }}>
        <fieldset disabled={busy}>
          <label htmlFor="item-title">标题</label>
          <input id="item-title" name="title" required maxLength={500}
            value={draft.title} onChange={event => update('title', event.target.value)} />
          {draft.title.length > 0 && !draft.title.trim() && (
            <p className="field-error" role="alert">标题不能只包含空白字符。</p>
          )}
          <div className="form-grid">
            <div>
              <label htmlFor="urgency">紧急程度</label>
              <select id="urgency" value={draft.urgency} onChange={event => update('urgency', event.target.value)}>
                <option value="">未设置</option><option value="true">紧急</option><option value="false">不紧急</option>
              </select>
            </div>
            <div>
              <label htmlFor="importance">重要程度</label>
              <select id="importance" value={draft.importance} onChange={event => update('importance', event.target.value)}>
                <option value="">未设置</option><option value="true">重要</option><option value="false">不重要</option>
              </select>
            </div>
            <div>
              <label htmlFor="due-on">目标完成日期</label>
              <input id="due-on" type="date" min="0001-01-01" max="9999-12-31"
                value={draft.dueOn} onChange={event => update('dueOn', event.target.value)} />
            </div>
            <div>
              <label htmlFor="color">颜色标记</label>
              <select id="color" value={draft.color} onChange={event => update('color', event.target.value)}>
                <option value="">无标记</option>
                {colors.map(color => <option key={color} value={color}>{colorLabels[color]}</option>)}
              </select>
            </div>
          </div>
          <label htmlFor="background">背景</label>
          <textarea id="background" rows={3} value={draft.background}
            onChange={event => update('background', event.target.value)} />
          <label htmlFor="goal">目标</label>
          <textarea id="goal" rows={3} value={draft.goal}
            onChange={event => update('goal', event.target.value)} />
          <button className="primary" type="submit" disabled={!draft.title.trim()}>
            {busy ? '正在处理…' : '创建工作项'}
          </button>
        </fieldset>
      </form>
      {error && <p role="alert" className="error">{error}</p>}
      {created && <p role="status" className="status success">工作项已创建</p>}
    </section>
  )
}
