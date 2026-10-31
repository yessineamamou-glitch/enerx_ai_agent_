import { Lock } from 'lucide-react'
import type { DeployState, Holdings, NewProjectInput, ProductionEvent, Profile, Project } from '@/lib/enerx/types'
import { Panel, SectionHeader } from '../primitives'
import { ProductionSimulator } from './production-simulator'
import { ProjectForm } from './project-form'

interface OwnerTabProps {
  activeProfile: Profile
  profiles: Profile[]
  projects: Project[]
  holdings: Holdings
  deployState: DeployState
  history: ProductionEvent[]
  lastEvent: ProductionEvent | null
  isSimulating: boolean
  simulatedPayload: { energy_kwh: string; revenue: string }
  kycVerified: boolean
  onDeploy: (input: NewProjectInput) => Promise<boolean>
  onResetDeploy: () => void
  onSimulate: (projectId: string) => void
}

export function OwnerTab(props: OwnerTabProps) {
  const { activeProfile } = props
  const ownedProjects = props.projects.filter((p) => p.ownerId === activeProfile.id)

  return (
    <div className="enerx-grid-bg">
      <div className="mx-auto flex max-w-7xl flex-col gap-10 px-4 py-10 md:px-6 md:py-14">
        <SectionHeader
          eyebrow="Participant workspace"
          title="Tokenize & operate your installation"
          description="Deploy an HTS token for your photovoltaic array, then stream verified STEG injection data to the HSCS revenue-split contract."
        />

        {!props.kycVerified ? (
          <Panel className="flex flex-col items-center gap-4 px-6 py-16 text-center">
            <span className="flex size-12 items-center justify-center rounded-xl bg-slate-800 ring-1 ring-white/10">
              <Lock className="size-5 text-slate-400" aria-hidden />
            </span>
            <div>
              <p className="text-lg font-semibold text-white">Project-owner verification required</p>
              <p className="mt-1 max-w-md text-sm text-slate-400">
                Complete the identity verification and obtain a valid ProjectOwner credential to create projects and run
                production simulations.
              </p>
            </div>
          </Panel>
        ) : (
          <>
            <ProjectForm deployState={props.deployState} onDeploy={props.onDeploy} onReset={props.onResetDeploy} />
            <ProductionSimulator
              projects={ownedProjects}
              history={props.history}
              lastEvent={props.lastEvent}
              isSimulating={props.isSimulating}
              payload={props.simulatedPayload}
              onSimulate={props.onSimulate}
            />
          </>
        )}
      </div>
    </div>
  )
}
