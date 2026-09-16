'use client'

import { createContext, useContext, useMemo, useReducer, type ReactNode } from 'react'
import type { AppliedContextItem, DashboardState, UIAction } from '../types/api'
import { applyUiActions, initialDashboardState, removeAppliedContext } from './uiActionDispatcher'

type StoreEvent =
  | { type: 'APPLY_AI_ACTIONS'; actions: UIAction[] }
  | { type: 'APPLY_DASHBOARD_AI_ACTIONS'; actions: UIAction[] }
  | { type: 'UNDO_AI_CHANGES' }
  | { type: 'SET_FILTER'; target: string; values: string[] }
  | { type: 'REMOVE_APPLIED_CONTEXT'; kind: AppliedContextItem['kind']; target: string }
  | { type: 'RESET' }

type DashboardStoreState = {
  currentDashboardState: DashboardState
  previousDashboardState: DashboardState | null
  aiAppliedActions: UIAction[]
}

const initialStoreState: DashboardStoreState = {
  currentDashboardState: initialDashboardState,
  previousDashboardState: null,
  aiAppliedActions: [],
}

function reducer(store: DashboardStoreState, event: StoreEvent): DashboardStoreState {
  const state = store.currentDashboardState
  switch (event.type) {
    case 'APPLY_AI_ACTIONS': return withoutAiTransaction(applyUiActions(state, event.actions))
    case 'APPLY_DASHBOARD_AI_ACTIONS': {
      if (!event.actions.length) return store
      return {
        currentDashboardState: applyUiActions(state, event.actions),
        previousDashboardState: state,
        aiAppliedActions: event.actions,
      }
    }
    case 'UNDO_AI_CHANGES': {
      if (!store.previousDashboardState) return store
      return withoutAiTransaction({ ...store.previousDashboardState, revision: state.revision + 1 })
    }
    case 'SET_FILTER': return withoutAiTransaction({ ...state, filters: { ...state.filters, [event.target]: event.values }, revision: state.revision + 1 })
    case 'REMOVE_APPLIED_CONTEXT': return withoutAiTransaction(removeAppliedContext(state, event.kind, event.target))
    case 'RESET': return withoutAiTransaction({ ...initialDashboardState, revision: state.revision + 1 })
  }
}

function withoutAiTransaction(state: DashboardState): DashboardStoreState {
  return { currentDashboardState: state, previousDashboardState: null, aiAppliedActions: [] }
}

type DashboardContextValue = {
  state: DashboardState
  previousDashboardState: DashboardState | null
  aiAppliedActions: UIAction[]
  applyActions: (actions: UIAction[]) => void
  applyDashboardAiActions: (actions: UIAction[]) => void
  undoAiChanges: () => void
  setFilter: (target: string, values: string[]) => void
  removeAppliedContext: (kind: AppliedContextItem['kind'], target: string) => void
  reset: () => void
}

const DashboardContext = createContext<DashboardContextValue | null>(null)

export function DashboardStateProvider({ children }: { children: ReactNode }) {
  const [store, dispatch] = useReducer(reducer, initialStoreState)
  const value = useMemo(() => ({
    state: store.currentDashboardState,
    previousDashboardState: store.previousDashboardState,
    aiAppliedActions: store.aiAppliedActions,
    applyActions: (actions: UIAction[]) => dispatch({ type: 'APPLY_AI_ACTIONS', actions }),
    applyDashboardAiActions: (actions: UIAction[]) => dispatch({ type: 'APPLY_DASHBOARD_AI_ACTIONS', actions }),
    undoAiChanges: () => dispatch({ type: 'UNDO_AI_CHANGES' }),
    setFilter: (target: string, values: string[]) => dispatch({ type: 'SET_FILTER', target, values }),
    removeAppliedContext: (kind: AppliedContextItem['kind'], target: string) => dispatch({ type: 'REMOVE_APPLIED_CONTEXT', kind, target }),
    reset: () => dispatch({ type: 'RESET' }),
  }), [store])
  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>
}

export function useDashboardState() {
  const context = useContext(DashboardContext)
  if (!context) throw new Error('useDashboardState must be used inside DashboardStateProvider')
  return context
}
