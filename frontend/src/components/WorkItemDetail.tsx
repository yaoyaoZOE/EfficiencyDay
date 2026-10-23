import type { WorkItem } from '../api/client'
import { colorLabels } from './WorkItemForm'

export const statusLabels = {
  pending: '待开始', in_progress: '进行中', completed: '已完成', cancelled: '已取消',
}

export function classification(item: WorkItem): string {
  if (item.urgency === null || item.importance === null) return '待分类'
  return `${item.urgency ? '紧急' : '不紧急'} · ${item.importance ? '重要' : '不重要'}`
}

function timestamp(value: string, timezone: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: timezone, dateStyle: 'medium', timeStyle: 'short',
  }).format(new Date(value))
}

export function WorkItemDetail({ item, timezone }: { item: WorkItem; timezone: string }) {
  return (
    <>
      <h3 className="detail-title">{item.title}</h3>
      <p><span className="badge">{statusLabels[item.status]}</span> {classification(item)}</p>
      <dl className="detail-facts">
        <div><dt>目标完成日期</dt><dd>{item.due_on ?? '未设置'}</dd></div>
        <div><dt>开始日期</dt><dd>{item.started_on ?? '尚未开始'}</dd></div>
        <div><dt>实际完成日期</dt><dd>{item.completed_on ?? '尚未完成'}</dd></div>
        <div><dt>颜色标记</dt><dd>{item.color_key ? colorLabels[item.color_key] : '无标记'}</dd></div>
        <div><dt>录入时间</dt><dd>{timestamp(item.created_at, timezone)}</dd></div>
        <div><dt>更新时间</dt><dd>{timestamp(item.updated_at, timezone)}</dd></div>
      </dl>
      <p className="muted">时间按 {timezone} 显示；日历日期不做时区转换。</p>
      {([
        ['背景', item.background], ['目标', item.goal],
        ['结果', item.result], ['复盘', item.reflection],
      ] as const).map(([label, value]) => (
        <div className="detail-section" key={label}>
          <h3>{label}</h3><p>{value || '暂无内容'}</p>
        </div>
      ))}
    </>
  )
}
