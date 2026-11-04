import type { CSSProperties } from 'react'

export function Skeleton({
  className = '',
  style,
}: {
  className?: string
  style?: CSSProperties
}) {
  return <div className={`skeleton ${className}`} style={style} aria-hidden="true" />
}

export function StatCardSkeleton() {
  return (
    <div className="card-raised p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="mt-3 h-7 w-32" />
        </div>
        <Skeleton className="h-9 w-9 rounded-lg" />
      </div>
      <Skeleton className="mt-3 h-3 w-40" />
    </div>
  )
}

export function ChartSkeleton({ height = 240 }: { height?: number }) {
  return (
    <div className="card p-5">
      <Skeleton className="h-4 w-44" />
      <Skeleton className="mt-4 w-full" />
      <div className="mt-4 flex items-end gap-2" style={{ height }}>
        {[40, 62, 48, 78, 55, 88, 70].map((value, index) => (
          <Skeleton
            key={index}
            className="flex-1"
            style={{ height: `${value}%`, alignSelf: 'flex-end' }}
          />
        ))}
      </div>
    </div>
  )
}

export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="card overflow-hidden">
      <div className="border-b border-navy-700/20 px-5 py-3">
        <Skeleton className="h-4 w-32" />
      </div>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex items-center gap-4 border-b border-navy-700/15 px-5 py-4">
          {Array.from({ length: cols }).map((__, colIndex) => (
            <Skeleton
              key={colIndex}
              className={`h-3.5 ${colIndex === 0 ? 'w-2/5' : colIndex === cols - 1 ? 'ml-auto w-20' : 'w-24'}`}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

export function ChatSkeleton() {
  return (
    <div className="card p-5">
      <Skeleton className="h-3 w-20" />
      <Skeleton className="mt-3 h-4 w-full" />
      <Skeleton className="mt-2 h-4 w-4/5" />
      <Skeleton className="mt-2 h-4 w-3/5" />
    </div>
  )
}
