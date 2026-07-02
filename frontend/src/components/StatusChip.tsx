import { statusVariant } from '../format';

const ACTIVE = ['live'];

export function StatusChip({ status }: { status: string }) {
  const v = statusVariant(status);
  return (
    <span className={`status-chip s-${v}`}>
      <span className={`dot ${ACTIVE.includes(v) ? 'pulse' : ''}`} />
      {status.toUpperCase()}
    </span>
  );
}
