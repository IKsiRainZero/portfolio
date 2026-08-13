import styles from './StatusDot.module.css'

interface Props {
  processing: boolean
  active: boolean
}

export default function StatusDot({ processing, active }: Props) {
  let cls = styles.dot
  if (processing) cls += ' ' + styles.processing
  else if (active) cls += ' ' + styles.active
  return <span className={cls} />
}
