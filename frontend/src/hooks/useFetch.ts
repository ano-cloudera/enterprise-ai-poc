'use client'

import { useEffect, useState, type DependencyList } from 'react'

export function useFetch<T>(loader: () => Promise<T>, dependencies: DependencyList = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    loader().then((value) => {
      if (active) setData(value)
    }).catch((err: Error) => {
      if (active) setError(err.message)
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, dependencies)

  return { data, error, loading, setData }
}
