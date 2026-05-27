export interface PaginationWindow<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

export function paginate<T>(
  items: T[],
  page: number,
  pageSize: number,
): PaginationWindow<T> {
  const start = Math.max(0, page * pageSize);
  const end = start + pageSize;

  return {
    items: items.slice(start, end),
    page,
    pageSize,
    total: items.length,
  };
}
