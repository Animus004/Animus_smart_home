package com.animus.smartroom.core.brain.router

/**
 * Dependency-aware execution planner that organizes actions into sequential stages
 * containing parallel independent tasks.
 */
object ExecutionPlanner {

    data class PlannedStage(
        val stageIndex: Int,
        val stageName: String,
        val actions: List<BrainIntent.DirectCommand>
    )

    data class ExecutionPlan(
        val correlationId: String,
        val routineName: String? = null,
        val stages: List<PlannedStage>
    )

    fun planRoutine(routine: BrainIntent.RoutineCommand): ExecutionPlan {
        val corrId = routine.correlationId
        return when (routine.routineName.uppercase()) {
            "MOVIE_MODE", "ROUTINE_MOVIE_MODE" -> ExecutionPlan(
                correlationId = corrId,
                routineName = "MOVIE_MODE",
                stages = listOf(
                    PlannedStage(
                        stageIndex = 1,
                        stageName = "Room Preparation & Power",
                        actions = listOf(
                            BrainIntent.DirectCommand(
                                target = CapabilityRegistry.DeviceTarget.PROJECTOR,
                                capability = CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON,
                                correlationId = corrId
                            ),
                            BrainIntent.DirectCommand(
                                target = CapabilityRegistry.DeviceTarget.FIRE_TV,
                                capability = CapabilityRegistry.ActionCapability.FIRE_TV_WAKE,
                                correlationId = corrId
                            ),
                            BrainIntent.DirectCommand(
                                target = CapabilityRegistry.DeviceTarget.AUDIO,
                                capability = CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG,
                                correlationId = corrId
                            )
                        )
                    ),
                    PlannedStage(
                        stageIndex = 2,
                        stageName = "Input Routing",
                        actions = listOf(
                            BrainIntent.DirectCommand(
                                target = CapabilityRegistry.DeviceTarget.PROJECTOR,
                                capability = CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT,
                                parameters = mapOf("input" to "HDMI_1"),
                                correlationId = corrId
                            )
                        )
                    )
                )
            )

            "MUSIC_MODE", "ROUTINE_MUSIC_MODE" -> ExecutionPlan(
                correlationId = corrId,
                routineName = "MUSIC_MODE",
                stages = listOf(
                    PlannedStage(
                        stageIndex = 1,
                        stageName = "Audio Connection",
                        actions = listOf(
                            BrainIntent.DirectCommand(
                                target = CapabilityRegistry.DeviceTarget.AUDIO,
                                capability = CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG,
                                correlationId = corrId
                            )
                        )
                    ),
                    PlannedStage(
                        stageIndex = 2,
                        stageName = "Media Playback",
                        actions = listOf(
                            BrainIntent.DirectCommand(
                                target = CapabilityRegistry.DeviceTarget.MEDIA,
                                capability = CapabilityRegistry.ActionCapability.MEDIA_PLAY,
                                parameters = routine.parameters,
                                correlationId = corrId
                            )
                        )
                    )
                )
            )

            "WORK_MODE", "ROUTINE_WORK_MODE" -> ExecutionPlan(
                correlationId = corrId,
                routineName = "WORK_MODE",
                stages = listOf(
                    PlannedStage(
                        stageIndex = 1,
                        stageName = "Climate Optimization",
                        actions = listOf(
                            BrainIntent.DirectCommand(
                                target = CapabilityRegistry.DeviceTarget.AC,
                                capability = CapabilityRegistry.ActionCapability.AC_POWER_ON,
                                correlationId = corrId
                            ),
                            BrainIntent.DirectCommand(
                                target = CapabilityRegistry.DeviceTarget.AC,
                                capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
                                parameters = mapOf("temperature" to 23),
                                correlationId = corrId
                            )
                        )
                    )
                )
            )

            "GOODNIGHT_MODE", "ROUTINE_GOODNIGHT_MODE", "SLEEP_ROUTINE" -> ExecutionPlan(
                correlationId = corrId,
                routineName = "GOODNIGHT_MODE",
                stages = listOf(
                    PlannedStage(
                        stageIndex = 1,
                        stageName = "Entertainment Shutdown",
                        actions = listOf(
                            BrainIntent.DirectCommand(
                                target = CapabilityRegistry.DeviceTarget.MEDIA,
                                capability = CapabilityRegistry.ActionCapability.MEDIA_STOP,
                                correlationId = corrId
                            ),
                            BrainIntent.DirectCommand(
                                target = CapabilityRegistry.DeviceTarget.PROJECTOR,
                                capability = CapabilityRegistry.ActionCapability.PROJECTOR_POWER_OFF,
                                correlationId = corrId
                            ),
                            BrainIntent.DirectCommand(
                                target = CapabilityRegistry.DeviceTarget.AUDIO,
                                capability = CapabilityRegistry.ActionCapability.AUDIO_DISCONNECT_LG,
                                correlationId = corrId
                            )
                        )
                    ),
                    PlannedStage(
                        stageIndex = 2,
                        stageName = "Night Climate Setting",
                        actions = listOf(
                            BrainIntent.DirectCommand(
                                target = CapabilityRegistry.DeviceTarget.AC,
                                capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
                                parameters = mapOf("temperature" to 24),
                                correlationId = corrId
                            )
                        )
                    )
                )
            )

            else -> ExecutionPlan(
                correlationId = corrId,
                routineName = routine.routineName,
                stages = emptyList()
            )
        }
    }

    fun planMultiAction(multi: BrainIntent.MultiActionCommand): ExecutionPlan {
        val corrId = multi.correlationId
        val independentActions = mutableListOf<BrainIntent.DirectCommand>()
        val dependentActions = mutableListOf<BrainIntent.DirectCommand>()

        for (action in multi.actions) {
            // Projector input setting depends on projector power on
            if (action.capability == CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT) {
                dependentActions.add(action)
            } else {
                independentActions.add(action)
            }
        }

        val stages = mutableListOf<PlannedStage>()
        if (independentActions.isNotEmpty()) {
            stages.add(
                PlannedStage(
                    stageIndex = 1,
                    stageName = "Independent Actions",
                    actions = independentActions
                )
            )
        }
        if (dependentActions.isNotEmpty()) {
            stages.add(
                PlannedStage(
                    stageIndex = stages.size + 1,
                    stageName = "Dependent Actions",
                    actions = dependentActions
                )
            )
        }

        return ExecutionPlan(
            correlationId = corrId,
            stages = stages
        )
    }
}
