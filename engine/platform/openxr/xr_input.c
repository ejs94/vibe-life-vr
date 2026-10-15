#include "common.h"
#include "xr_input.h"
#include "xr_core.h"
#include "xr_swapchain.h"
#include "const.h"
#include "client.h"
#include "keydefs.h"
#include "input.h"
#include "vgui_draw.h"
#include <openxr/openxr.h>
#include <string.h>
#include <math.h>

#ifdef XASH_OPENXR

xr_input_state_t g_xrInputState = {0};

static XrActionSet g_actionSet = XR_NULL_HANDLE;
static XrAction g_actionAttack = XR_NULL_HANDLE;
static XrAction g_actionAttack2 = XR_NULL_HANDLE;
static XrAction g_actionGripLeft = XR_NULL_HANDLE;
static XrAction g_actionGripRight = XR_NULL_HANDLE;
static XrAction g_actionJump = XR_NULL_HANDLE;
static XrAction g_actionDuck = XR_NULL_HANDLE;
static XrAction g_actionUse = XR_NULL_HANDLE;
static XrAction g_actionReload = XR_NULL_HANDLE;
static XrAction g_actionFlashlight = XR_NULL_HANDLE;
static XrAction g_actionMenu = XR_NULL_HANDLE;
static XrAction g_actionSprint = XR_NULL_HANDLE;
static XrAction g_actionMove = XR_NULL_HANDLE;
static XrAction g_actionTurn = XR_NULL_HANDLE;
static XrAction g_actionAimPoseLeft = XR_NULL_HANDLE;
static XrAction g_actionAimPoseRight = XR_NULL_HANDLE;
static XrAction g_actionHapticLeft = XR_NULL_HANDLE;
static XrAction g_actionHapticRight = XR_NULL_HANDLE;

static float s_playerTurnYaw = 0.0f;

float XR_GetPlayerTurnYaw( void )
{
    return s_playerTurnYaw;
}


static XrSpace g_leftHandSpace = XR_NULL_HANDLE;
static XrSpace g_rightHandSpace = XR_NULL_HANDLE;

static XrPath StringToPath( const char *str )
{
    XrPath path = XR_NULL_PATH;
    if (g_xrInstance != XR_NULL_HANDLE)
    {
        xrStringToPath(g_xrInstance, str, &path);
    }
    return path;
}

static XrAction CreateAction( const char *actionName, const char *localizedName, XrActionType type )
{
    XrActionCreateInfo actionInfo = {0};
    actionInfo.type = XR_TYPE_ACTION_CREATE_INFO;
    actionInfo.actionType = type;
    strncpy(actionInfo.actionName, actionName, XR_MAX_ACTION_NAME_SIZE - 1);
    strncpy(actionInfo.localizedActionName, localizedName, XR_MAX_LOCALIZED_ACTION_NAME_SIZE - 1);

    XrAction action = XR_NULL_HANDLE;
    xrCreateAction(g_actionSet, &actionInfo, &action);
    return action;
}

static void XR_Haptic_f( void );

qboolean XR_InitInput( void )
{
    if (g_xrInstance == XR_NULL_HANDLE || g_xrSession == XR_NULL_HANDLE)
    {
        return false;
    }

    Con_Printf("XR_InitInput: Creating Khronos Action Sets...\n");

    XrActionSetCreateInfo actionSetInfo = {0};
    actionSetInfo.type = XR_TYPE_ACTION_SET_CREATE_INFO;
    strcpy(actionSetInfo.actionSetName, "gameplay");
    strcpy(actionSetInfo.localizedActionSetName, "Gameplay");
    actionSetInfo.priority = 0;

    if (XR_FAILED(xrCreateActionSet(g_xrInstance, &actionSetInfo, &g_actionSet)))
    {
        Con_Printf("XR_InitInput: Failed to create action set!\n");
        return false;
    }

    // Create Actions
    g_actionAttack      = CreateAction("attack", "Attack", XR_ACTION_TYPE_FLOAT_INPUT);
    g_actionAttack2     = CreateAction("attack2", "Secondary Attack", XR_ACTION_TYPE_FLOAT_INPUT);
    g_actionGripLeft    = CreateAction("grip_left", "Left Hand Grip", XR_ACTION_TYPE_FLOAT_INPUT);
    g_actionGripRight   = CreateAction("grip_right", "Right Hand Grip", XR_ACTION_TYPE_FLOAT_INPUT);
    g_actionJump        = CreateAction("jump", "Jump", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionDuck        = CreateAction("duck", "Crouch", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionUse         = CreateAction("use", "Use / Interact", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionReload      = CreateAction("reload", "Reload", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionFlashlight  = CreateAction("flashlight", "Flashlight (impulse 100)", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionMenu        = CreateAction("menu_toggle", "Menu / Pause", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionSprint      = CreateAction("sprint", "Sprint", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionMove        = CreateAction("move", "Move (Locomotion)", XR_ACTION_TYPE_VECTOR2F_INPUT);
    g_actionTurn        = CreateAction("turn", "Turn (Snap/Smooth)", XR_ACTION_TYPE_VECTOR2F_INPUT);
    g_actionAimPoseLeft = CreateAction("aim_left", "Left Aim Pose", XR_ACTION_TYPE_POSE_INPUT);
    g_actionAimPoseRight= CreateAction("aim_right", "Right Aim Pose", XR_ACTION_TYPE_POSE_INPUT);
    g_actionHapticLeft  = CreateAction("haptic_left", "Left Hand Haptics", XR_ACTION_TYPE_VIBRATION_OUTPUT);
    g_actionHapticRight = CreateAction("haptic_right", "Right Hand Haptics", XR_ACTION_TYPE_VIBRATION_OUTPUT);

    // Map Oculus / Meta Quest Touch Controller profile
    XrPath oculusProfile = StringToPath("/interaction_profiles/oculus/touch_controller");
    XrActionSuggestedBinding oculusBindings[] = {
        { g_actionAttack,       StringToPath("/user/hand/right/input/trigger/value") },
        { g_actionAttack2,      StringToPath("/user/hand/left/input/trigger/value") },
        { g_actionGripRight,    StringToPath("/user/hand/right/input/squeeze/value") },
        { g_actionGripLeft,     StringToPath("/user/hand/left/input/squeeze/value") },
        { g_actionJump,         StringToPath("/user/hand/right/input/a/click") },
        { g_actionDuck,         StringToPath("/user/hand/right/input/thumbstick/click") },
        { g_actionUse,          StringToPath("/user/hand/right/input/b/click") },
        { g_actionReload,       StringToPath("/user/hand/left/input/x/click") },
        { g_actionFlashlight,   StringToPath("/user/hand/left/input/y/click") },
        { g_actionMenu,         StringToPath("/user/hand/left/input/menu/click") },
        { g_actionSprint,       StringToPath("/user/hand/left/input/thumbstick/click") },
        { g_actionMove,         StringToPath("/user/hand/left/input/thumbstick") },
        { g_actionTurn,         StringToPath("/user/hand/right/input/thumbstick") },
        { g_actionAimPoseLeft,  StringToPath("/user/hand/left/input/aim/pose") },
        { g_actionAimPoseRight, StringToPath("/user/hand/right/input/aim/pose") },
        { g_actionHapticLeft,   StringToPath("/user/hand/left/output/haptic") },
        { g_actionHapticRight,  StringToPath("/user/hand/right/output/haptic") },
    };

    XrInteractionProfileSuggestedBinding suggestedBindings = {0};
    suggestedBindings.type = XR_TYPE_INTERACTION_PROFILE_SUGGESTED_BINDING;
    suggestedBindings.interactionProfile = oculusProfile;
    suggestedBindings.suggestedBindings = oculusBindings;
    suggestedBindings.countSuggestedBindings = sizeof(oculusBindings) / sizeof(oculusBindings[0]);

    XrResult resOculus = xrSuggestInteractionProfileBindings(g_xrInstance, &suggestedBindings);
    Con_Printf("XR_InitInput: Oculus Touch suggested bindings res = %d\n", resOculus);

    // Map Meta Quest 3 Touch Plus Controller profile
    XrPath touchPlusProfile = StringToPath("/interaction_profiles/meta/touch_plus_controller");
    if (touchPlusProfile != XR_NULL_PATH)
    {
        suggestedBindings.interactionProfile = touchPlusProfile;
        XrResult resPlus = xrSuggestInteractionProfileBindings(g_xrInstance, &suggestedBindings);
        Con_Printf("XR_InitInput: Touch Plus suggested bindings res = %d\n", resPlus);
    }

    // Map Meta Quest Pro Controller profile
    XrPath touchProProfile = StringToPath("/interaction_profiles/meta/touch_pro_controller");
    if (touchProProfile != XR_NULL_PATH)
    {
        suggestedBindings.interactionProfile = touchProProfile;
        XrResult resPro = xrSuggestInteractionProfileBindings(g_xrInstance, &suggestedBindings);
        Con_Printf("XR_InitInput: Touch Pro suggested bindings res = %d\n", resPro);
    }

    // Map Valve Index Controller profile
    XrPath indexProfile = StringToPath("/interaction_profiles/valve/index_controller");
    XrActionSuggestedBinding indexBindings[] = {
        { g_actionAttack,       StringToPath("/user/hand/right/input/trigger/value") },
        { g_actionAttack2,      StringToPath("/user/hand/left/input/trigger/value") },
        { g_actionGripRight,    StringToPath("/user/hand/right/input/squeeze/value") },
        { g_actionGripLeft,     StringToPath("/user/hand/left/input/squeeze/value") },
        { g_actionJump,         StringToPath("/user/hand/right/input/a/click") },
        { g_actionDuck,         StringToPath("/user/hand/right/input/thumbstick/click") },
        { g_actionUse,          StringToPath("/user/hand/right/input/b/click") },
        { g_actionReload,       StringToPath("/user/hand/left/input/a/click") },
        { g_actionFlashlight,   StringToPath("/user/hand/left/input/b/click") },
        { g_actionSprint,       StringToPath("/user/hand/left/input/thumbstick/click") },
        { g_actionMove,         StringToPath("/user/hand/left/input/thumbstick") },
        { g_actionTurn,         StringToPath("/user/hand/right/input/thumbstick") },
        { g_actionAimPoseLeft,  StringToPath("/user/hand/left/input/aim/pose") },
        { g_actionAimPoseRight, StringToPath("/user/hand/right/input/aim/pose") },
        { g_actionHapticLeft,   StringToPath("/user/hand/left/output/haptic") },
        { g_actionHapticRight,  StringToPath("/user/hand/right/output/haptic") },
    };
    suggestedBindings.interactionProfile = indexProfile;
    suggestedBindings.suggestedBindings = indexBindings;
    suggestedBindings.countSuggestedBindings = sizeof(indexBindings) / sizeof(indexBindings[0]);

    XrResult resIndex = xrSuggestInteractionProfileBindings(g_xrInstance, &suggestedBindings);
    Con_Printf("XR_InitInput: Valve Index suggested bindings res = %d\n", resIndex);

    // Attach Action Set to Session
    XrSessionActionSetsAttachInfo attachInfo = {0};
    attachInfo.type = XR_TYPE_SESSION_ACTION_SETS_ATTACH_INFO;
    attachInfo.countActionSets = 1;
    attachInfo.actionSets = &g_actionSet;

    XrResult resAttach = xrAttachSessionActionSets(g_xrSession, &attachInfo);
    if (XR_FAILED(resAttach))
    {
        Con_Printf("XR_InitInput: Failed to attach Action Set to session (res = %d)!\n", resAttach);
        return false;
    }
    Con_Printf("XR_InitInput: Action Set attached successfully!\n");

    // Create Action Spaces for hand poses
    XrActionSpaceCreateInfo spaceInfo = {0};
    spaceInfo.type = XR_TYPE_ACTION_SPACE_CREATE_INFO;
    spaceInfo.poseInActionSpace.orientation.w = 1.0f;

    spaceInfo.action = g_actionAimPoseLeft;
    xrCreateActionSpace(g_xrSession, &spaceInfo, &g_leftHandSpace);

    spaceInfo.action = g_actionAimPoseRight;
    xrCreateActionSpace(g_xrSession, &spaceInfo, &g_rightHandSpace);

    Cmd_AddCommand("vr_haptic", XR_Haptic_f, "Trigger OpenXR haptic vibration: vr_haptic <left|right|both> [duration] [freq] [amplitude]");

    Con_Printf("XR_InitInput: VR interaction profiles and action sets initialized successfully!\n");
    return true;
}

void XR_ShutdownInput( void )
{
    Cmd_RemoveCommand("vr_haptic");

    if (g_leftHandSpace != XR_NULL_HANDLE)
    {
        xrDestroySpace(g_leftHandSpace);
        g_leftHandSpace = XR_NULL_HANDLE;
    }
    if (g_rightHandSpace != XR_NULL_HANDLE)
    {
        xrDestroySpace(g_rightHandSpace);
        g_rightHandSpace = XR_NULL_HANDLE;
    }
    if (g_actionSet != XR_NULL_HANDLE)
    {
        xrDestroyActionSet(g_actionSet);
        g_actionSet = XR_NULL_HANDLE;
    }
    g_actionAttack = XR_NULL_HANDLE;
    g_actionAttack2 = XR_NULL_HANDLE;
    g_actionGripLeft = XR_NULL_HANDLE;
    g_actionGripRight = XR_NULL_HANDLE;
    g_actionJump = XR_NULL_HANDLE;
    g_actionDuck = XR_NULL_HANDLE;
    g_actionUse = XR_NULL_HANDLE;
    g_actionReload = XR_NULL_HANDLE;
    g_actionFlashlight = XR_NULL_HANDLE;
    g_actionMenu = XR_NULL_HANDLE;
    g_actionSprint = XR_NULL_HANDLE;
    g_actionMove = XR_NULL_HANDLE;
    g_actionTurn = XR_NULL_HANDLE;
    g_actionAimPoseLeft = XR_NULL_HANDLE;
    g_actionAimPoseRight = XR_NULL_HANDLE;
    g_actionHapticLeft = XR_NULL_HANDLE;
    g_actionHapticRight = XR_NULL_HANDLE;
}

void XR_SyncInputs( void )
{
    if (!g_xrSessionRunning || g_actionSet == XR_NULL_HANDLE) return;

    XrActiveActionSet activeSet = {0};
    activeSet.actionSet = g_actionSet;
    activeSet.subactionPath = XR_NULL_PATH;

    XrActionsSyncInfo syncInfo = {0};
    syncInfo.type = XR_TYPE_ACTIONS_SYNC_INFO;
    syncInfo.countActiveActionSets = 1;
    syncInfo.activeActionSets = &activeSet;

    XrResult syncRes = xrSyncActions(g_xrSession, &syncInfo);
    if (XR_FAILED(syncRes))
    {
        static double last_sync_warn = 0;
        if (Platform_DoubleTime() - last_sync_warn > 3.0)
        {
            Con_Printf("XR_SyncInputs: xrSyncActions failed (res = %d)\n", syncRes);
            last_sync_warn = Platform_DoubleTime();
        }
        return;
    }

    // Leitura dos gatilhos analógicos e grips
    XrActionStateGetInfo getInfo = {0};
    getInfo.type = XR_TYPE_ACTION_STATE_GET_INFO;

    XrActionStateFloat floatState = {0};
    floatState.type = XR_TYPE_ACTION_STATE_FLOAT;

    getInfo.action = g_actionAttack;
    if (XR_SUCCEEDED(xrGetActionStateFloat(g_xrSession, &getInfo, &floatState)))
        g_xrInputState.attack = (floatState.currentState > 0.5f);

    getInfo.action = g_actionAttack2;
    if (XR_SUCCEEDED(xrGetActionStateFloat(g_xrSession, &getInfo, &floatState)))
        g_xrInputState.attack2 = (floatState.currentState > 0.5f);

    if (g_actionGripRight != XR_NULL_HANDLE)
    {
        getInfo.action = g_actionGripRight;
        if (XR_SUCCEEDED(xrGetActionStateFloat(g_xrSession, &getInfo, &floatState)))
        {
            g_xrInputState.gripRight = floatState.currentState;
            if (floatState.currentState > 0.5f)
                g_xrInputState.use = true;
        }
    }

    if (g_actionGripLeft != XR_NULL_HANDLE)
    {
        getInfo.action = g_actionGripLeft;
        if (XR_SUCCEEDED(xrGetActionStateFloat(g_xrSession, &getInfo, &floatState)))
        {
            g_xrInputState.gripLeft = floatState.currentState;
        }
    }

    // Leitura dos botões digitais
    XrActionStateBoolean boolState = {0};
    boolState.type = XR_TYPE_ACTION_STATE_BOOLEAN;

    getInfo.action = g_actionJump;
    if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
        g_xrInputState.jump = boolState.currentState;

    getInfo.action = g_actionDuck;
    if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
        g_xrInputState.duck = boolState.currentState;

    getInfo.action = g_actionUse;
    if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
    {
        if (boolState.currentState)
            g_xrInputState.use = true;
    }

    getInfo.action = g_actionReload;
    if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
        g_xrInputState.reload = boolState.currentState;

    if (g_actionFlashlight != XR_NULL_HANDLE)
    {
        getInfo.action = g_actionFlashlight;
        if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
            g_xrInputState.flashlight = boolState.currentState;
    }

    if (g_actionMenu != XR_NULL_HANDLE)
    {
        getInfo.action = g_actionMenu;
        if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
            g_xrInputState.menu = boolState.currentState;
    }

    if (g_actionSprint != XR_NULL_HANDLE)
    {
        getInfo.action = g_actionSprint;
        if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
            g_xrInputState.sprint = boolState.currentState;
    }


    // Leitura dos sticks analógicos
    XrActionStateVector2f vecState = {0};
    vecState.type = XR_TYPE_ACTION_STATE_VECTOR2F;

    getInfo.action = g_actionMove;
    if (XR_SUCCEEDED(xrGetActionStateVector2f(g_xrSession, &getInfo, &vecState)))
    {
        float deadzone = 0.15f;
        g_xrInputState.moveX = (fabsf(vecState.currentState.x) > deadzone) ? vecState.currentState.x : 0.0f;
        g_xrInputState.moveY = (fabsf(vecState.currentState.y) > deadzone) ? vecState.currentState.y : 0.0f;
    }

    getInfo.action = g_actionTurn;
    if (XR_SUCCEEDED(xrGetActionStateVector2f(g_xrSession, &getInfo, &vecState)))
    {
        float deadzone = 0.15f;
        g_xrInputState.turnX = (fabsf(vecState.currentState.x) > deadzone) ? vecState.currentState.x : 0.0f;
        g_xrInputState.turnY = (fabsf(vecState.currentState.y) > deadzone) ? vecState.currentState.y : 0.0f;
    }

    // Leitura das poses e velocidades das mãos (6DoF)
    XrTime syncTime = XR_GetPredictedDisplayTime();
    if (syncTime > 0)
    {
        if (g_leftHandSpace != XR_NULL_HANDLE && g_xrLocalSpace != XR_NULL_HANDLE)
        {
            XrSpaceVelocity vel = {0};
            vel.type = XR_TYPE_SPACE_VELOCITY;
            XrSpaceLocation loc = {0};
            loc.type = XR_TYPE_SPACE_LOCATION;
            loc.next = &vel;
            if (XR_SUCCEEDED(xrLocateSpace(g_leftHandSpace, g_xrLocalSpace, syncTime, &loc)))
            {
                if (loc.locationFlags & XR_SPACE_LOCATION_POSITION_VALID_BIT)
                {
                    g_xrInputState.leftHandPose = loc.pose;
                    g_xrInputState.leftHandActive = true;
                }
                if (vel.velocityFlags & XR_SPACE_VELOCITY_LINEAR_VALID_BIT)
                {
                    g_xrInputState.leftHandVelocity = vel.linearVelocity;
                }
            }
        }

        if (g_rightHandSpace != XR_NULL_HANDLE && g_xrLocalSpace != XR_NULL_HANDLE)
        {
            XrSpaceVelocity vel = {0};
            vel.type = XR_TYPE_SPACE_VELOCITY;
            XrSpaceLocation loc = {0};
            loc.type = XR_TYPE_SPACE_LOCATION;
            loc.next = &vel;
            if (XR_SUCCEEDED(xrLocateSpace(g_rightHandSpace, g_xrLocalSpace, syncTime, &loc)))
            {
                if (loc.locationFlags & XR_SPACE_LOCATION_POSITION_VALID_BIT)
                {
                    g_xrInputState.rightHandPose = loc.pose;
                    g_xrInputState.rightHandActive = true;
                }
                if (vel.velocityFlags & XR_SPACE_VELOCITY_LINEAR_VALID_BIT)
                {
                    g_xrInputState.rightHandVelocity = vel.linearVelocity;
                }
            }
        }
    }
}

void XR_InputAppendMove( usercmd_t *cmd, float frametime )
{
    if (!g_xrSessionRunning) return;

    qboolean lefthanded = (vr_lefthanded && vr_lefthanded->value > 0.0f);

    float rawMoveX = lefthanded ? g_xrInputState.turnX : g_xrInputState.moveX;
    float rawMoveY = lefthanded ? g_xrInputState.turnY : g_xrInputState.moveY;
    float rawTurnX = lefthanded ? g_xrInputState.moveX : g_xrInputState.turnX;
    float rawTurnY = lefthanded ? g_xrInputState.moveY : g_xrInputState.turnY;

    qboolean attack  = lefthanded ? g_xrInputState.attack2 : g_xrInputState.attack;
    qboolean attack2 = lefthanded ? g_xrInputState.attack  : g_xrInputState.attack2;

    // Aplicar botões de ação
    if (attack)                 cmd->buttons |= IN_ATTACK;
    if (attack2)                cmd->buttons |= IN_ATTACK2;
    if (g_xrInputState.jump)    cmd->buttons |= IN_JUMP;
    if (g_xrInputState.duck)    cmd->buttons |= IN_DUCK;
    if (g_xrInputState.use)     cmd->buttons |= IN_USE;
    if (g_xrInputState.reload)  cmd->buttons |= IN_RELOAD;
    if (g_xrInputState.sprint)  cmd->buttons |= IN_RUN;

    // Flashlight Toggle (impulse 100) via Y button (or Index B)
    static qboolean s_prevFlashlight = false;
    if (g_xrInputState.flashlight && !s_prevFlashlight)
    {
        s_prevFlashlight = true;
        Cbuf_AddText("impulse 100\n");
        XR_TriggerHapticEffect(VR_HAND_LEFT, VR_HAPTIC_UI_CLICK, 0.4f);
    }
    else if (!g_xrInputState.flashlight && s_prevFlashlight)
    {
        s_prevFlashlight = false;
    }

    // In-Game Menu Toggle (cancelselect) via Left Controller Menu button
    static qboolean s_prevMenu = false;
    if (g_xrInputState.menu && !s_prevMenu)
    {
        s_prevMenu = true;
        Cbuf_AddText("cancelselect\n");
        XR_TriggerHapticEffect(VR_HAND_LEFT, VR_HAPTIC_UI_CLICK, 0.5f);
    }
    else if (!g_xrInputState.menu && s_prevMenu)
    {
        s_prevMenu = false;
    }

    // Weapon cycling via turn thumbstick flick (Up: invprev, Down: invnext)
    static double s_nextWeaponSwitchTime = 0.0;
    if (host.realtime >= s_nextWeaponSwitchTime)
    {
        if (rawTurnY > 0.65f)
        {
            Cbuf_AddText("invprev\n");
            XR_TriggerHapticEffect(lefthanded ? VR_HAND_LEFT : VR_HAND_RIGHT, VR_HAPTIC_UI_CLICK, 0.35f);
            s_nextWeaponSwitchTime = host.realtime + 0.25;
        }
        else if (rawTurnY < -0.65f)
        {
            Cbuf_AddText("invnext\n");
            XR_TriggerHapticEffect(lefthanded ? VR_HAND_LEFT : VR_HAND_RIGHT, VR_HAPTIC_UI_CLICK, 0.35f);
            s_nextWeaponSwitchTime = host.realtime + 0.25;
        }
    }

    // 1. Use Gesture (Esticar a mão para frente interage automaticamente com botões/portas)
    if ((-g_xrInputState.rightHandPose.position.z > 0.38f && fabsf(g_xrInputState.rightHandPose.position.y) < 0.35f) ||
        (-g_xrInputState.leftHandPose.position.z > 0.38f && fabsf(g_xrInputState.leftHandPose.position.y) < 0.35f))
    {
        cmd->buttons |= IN_USE;
    }

    // 2. Backpack Gesture (Mochila: mão dominante atrás do ombro saca pé de cabra)
    static qboolean backpack_debounced = false;
    XrPosef dominantPose = lefthanded ? g_xrInputState.leftHandPose : g_xrInputState.rightHandPose;
    if (dominantPose.position.z > 0.10f && dominantPose.position.y > -0.15f)
    {
        if (attack && !backpack_debounced)
        {
            Cbuf_AddText("slot1\n"); // Saca o Pé de Cabra / Crowbar!
            XR_TriggerHapticEffect(lefthanded ? VR_HAND_LEFT : VR_HAND_RIGHT, VR_HAPTIC_WEAPON_CROWBAR, 0.7f);
            backpack_debounced = true;
        }
    }
    else
    {
        backpack_debounced = false;
    }

    // Giro suave ou Snap Turn (Thumbstick de Giro)
    static qboolean s_yawInitialized = false;
    static qboolean snap_debounced = false;

    if (!s_yawInitialized && (cmd->viewangles[1] != 0.0f))
    {
        s_playerTurnYaw = cmd->viewangles[1];
        s_yawInitialized = true;
    }

    if (vr_smoothturn && vr_smoothturn->value == 0.0f)
    {
        float snapAngle = (vr_snap_angle && vr_snap_angle->value > 0.0f) ? vr_snap_angle->value : 45.0f;
        if (rawTurnX > 0.5f && !snap_debounced)
        {
            s_playerTurnYaw -= snapAngle;
            snap_debounced = true;
            XR_TriggerHapticEffect(lefthanded ? VR_HAND_LEFT : VR_HAND_RIGHT, VR_HAPTIC_UI_CLICK, 0.25f);
        }
        else if (rawTurnX < -0.5f && !snap_debounced)
        {
            s_playerTurnYaw += snapAngle;
            snap_debounced = true;
            XR_TriggerHapticEffect(lefthanded ? VR_HAND_LEFT : VR_HAND_RIGHT, VR_HAPTIC_UI_CLICK, 0.25f);
        }
        else if (fabsf(rawTurnX) < 0.2f)
        {
            snap_debounced = false;
        }
    }
    else
    {
        if (fabsf(rawTurnX) > 0.15f)
        {
            float turnSpeed = 150.0f; // graus por segundo
            s_playerTurnYaw -= rawTurnX * turnSpeed * frametime;
        }
    }
    s_playerTurnYaw = anglemod( s_playerTurnYaw );

    // Conectar poses 6DoF de mira do controle diretamente ao cmd->viewangles do servidor
    vec3_t handOrigin, handAngles;
    if (XR_GetPrimaryHandTransform( handOrigin, handAngles ))
    {
        vec3_t worldAimAngles;
        worldAimAngles[0] = handAngles[0];
        worldAimAngles[1] = anglemod( handAngles[1] + s_playerTurnYaw );
        worldAimAngles[2] = handAngles[2];

        // O ângulo de tiro do cano vai direto para a rotação de comando do servidor
        VectorCopy( worldAimAngles, cmd->viewangles );

        // Desacoplamento da locomoção:
        // vr_walkdirection 0: Orientado pelo Headset (padrão) | 1: Orientado pelo Controle
        vec3_t headAngles;
        XR_GetHeadOrientation( headAngles );
        float headWorldYaw = anglemod( headAngles[1] + s_playerTurnYaw );
        float walkRefYaw = (vr_walkdirection && vr_walkdirection->value == 1.0f) ? worldAimAngles[1] : headWorldYaw;

        float deltaYaw = walkRefYaw - worldAimAngles[1];
        float rad = deltaYaw * (3.14159265f / 180.0f);
        float cosA = cosf(rad);
        float sinA = sinf(rad);

        float forwardMove = rawMoveY * cosA - rawMoveX * sinA;
        float sideMove    = rawMoveY * sinA + rawMoveX * cosA;

        cmd->forwardmove += forwardMove * 320.0f;
        cmd->sidemove    += sideMove * 320.0f;
    }
    else
    {
        cmd->viewangles[1] = s_playerTurnYaw;
        cmd->forwardmove += rawMoveY * 320.0f;
        cmd->sidemove    += rawMoveX * 320.0f;
    }

    // Limitar para os máximos suportados pelo motor
    cmd->forwardmove = bound(-400.0f, cmd->forwardmove, 400.0f);
    cmd->sidemove    = bound(-400.0f, cmd->sidemove, 400.0f);
}

qboolean XR_GetPrimaryHandTransform( vec3_t out_origin, vec3_t out_angles )
{
    if (vr_lefthanded && vr_lefthanded->value > 0.0f)
        return XR_GetLeftHandTransform( out_origin, out_angles );
    return XR_GetRightHandTransform( out_origin, out_angles );
}

qboolean XR_GetPrimaryHandVelocity( vec3_t out_velocity )
{
    if (vr_lefthanded && vr_lefthanded->value > 0.0f)
        return XR_GetLeftHandVelocity( out_velocity );
    return XR_GetRightHandVelocity( out_velocity );
}

qboolean XR_GetPrimaryHandMuzzleTransform( vec3_t out_muzzle_offset, vec3_t out_aim_angles )
{
    if (!g_xrSessionRunning) return false;

    vec3_t handOrigin, handAngles;
    if (!XR_GetPrimaryHandTransform( handOrigin, handAngles )) return false;

    float scale = (vr_worldscale && vr_worldscale->value > 0.0f) ? vr_worldscale->value : 40.0f;

    vec3_t eyePos;
    XR_GetEyePosition( 0, eyePos );

    vec3_t relHand;
    relHand[0] = (handOrigin[0] - eyePos[0]) * scale;
    relHand[1] = (handOrigin[1] - eyePos[1]) * scale;
    relHand[2] = (handOrigin[2] - eyePos[2]) * scale;

    vec3_t forward;
    AngleVectors( handAngles, forward, NULL, NULL );

    out_muzzle_offset[0] = relHand[0] + forward[0] * 8.0f;
    out_muzzle_offset[1] = relHand[1] + forward[1] * 8.0f;
    out_muzzle_offset[2] = relHand[2] + forward[2] * 8.0f;

    VectorCopy( handAngles, out_aim_angles );
    return true;
}

qboolean XR_GetRightHandTransform( vec3_t out_origin, vec3_t out_angles )
{
    if (!g_xrSessionRunning) return false;

    if (!g_xrInputState.rightHandActive)
    {
        if (vr_test_hands && vr_test_hands->value > 0.0f)
        {
            out_origin[0] = 0.22f;   // 22cm à frente
            out_origin[1] = -0.06f;  // 6cm à direita (coordenadas GoldSrc)
            out_origin[2] = -0.08f;  // 8cm abaixo dos olhos

            out_angles[0] = vr_test_hand_pitch ? vr_test_hand_pitch->value : 0.0f;
            out_angles[1] = vr_test_hand_yaw ? vr_test_hand_yaw->value : 0.0f;
            out_angles[2] = 0.0f;

            if (vr_weapon_pitchadjust && vr_weapon_pitchadjust->value != 0.0f)
                out_angles[0] += vr_weapon_pitchadjust->value;
            if (vr_weapon_yawadjust && vr_weapon_yawadjust->value != 0.0f)
                out_angles[1] = anglemod(out_angles[1] + vr_weapon_yawadjust->value);
            if (vr_weapon_rolladjust && vr_weapon_rolladjust->value != 0.0f)
                out_angles[2] += vr_weapon_rolladjust->value;

            return true;
        }
        return false;
    }

    // Convert to GoldSrc coordinates:
    // X = forward (-Z), Y = left (-X), Z = up (Y)
    out_origin[0] = -g_xrInputState.rightHandPose.position.z;
    out_origin[1] = -g_xrInputState.rightHandPose.position.x;
    out_origin[2] = g_xrInputState.rightHandPose.position.y;

    // Two-Handed Weapon Stabiliser (active when left grip > 0.4 and distance is 12cm-55cm)
    float dx = g_xrInputState.leftHandPose.position.x - g_xrInputState.rightHandPose.position.x;
    float dy = g_xrInputState.leftHandPose.position.y - g_xrInputState.rightHandPose.position.y;
    float dz = g_xrInputState.leftHandPose.position.z - g_xrInputState.rightHandPose.position.z;
    float handDist = sqrtf(dx*dx + dy*dy + dz*dz);

    if (g_xrInputState.gripLeft > 0.4f && handDist >= 0.12f && handDist <= 0.55f && g_xrInputState.leftHandActive)
    {
        // Vector from rear hand (right) to front hand (left) in GoldSrc coordinates:
        vec3_t aimDir;
        aimDir[0] = (g_xrInputState.rightHandPose.position.z - g_xrInputState.leftHandPose.position.z);
        aimDir[1] = (g_xrInputState.rightHandPose.position.x - g_xrInputState.leftHandPose.position.x);
        aimDir[2] = (g_xrInputState.leftHandPose.position.y - g_xrInputState.rightHandPose.position.y);
        VectorNormalize(aimDir);
        VectorAngles(aimDir, out_angles);
    }
    else
    {
        XR_QuatToEuler( &g_xrInputState.rightHandPose.orientation, out_angles );
    }

    if (vr_weapon_pitchadjust && vr_weapon_pitchadjust->value != 0.0f)
    {
        out_angles[0] += vr_weapon_pitchadjust->value;
    }
    if (vr_weapon_yawadjust && vr_weapon_yawadjust->value != 0.0f)
    {
        out_angles[1] = anglemod(out_angles[1] + vr_weapon_yawadjust->value);
    }
    if (vr_weapon_rolladjust && vr_weapon_rolladjust->value != 0.0f)
    {
        out_angles[2] += vr_weapon_rolladjust->value;
    }

    return true;
}

qboolean XR_GetLeftHandTransform( vec3_t out_origin, vec3_t out_angles )
{
    if (!g_xrSessionRunning) return false;

    if (!g_xrInputState.leftHandActive)
    {
        if (vr_test_hands && vr_test_hands->value > 0.0f)
        {
            out_origin[0] = 0.22f;
            out_origin[1] = 0.06f;   // 6cm to the left
            out_origin[2] = -0.08f;

            out_angles[0] = vr_test_hand_pitch ? vr_test_hand_pitch->value : 0.0f;
            out_angles[1] = vr_test_hand_yaw ? vr_test_hand_yaw->value : 0.0f;
            out_angles[2] = 0.0f;

            if (vr_weapon_pitchadjust && vr_weapon_pitchadjust->value != 0.0f)
                out_angles[0] += vr_weapon_pitchadjust->value;
            if (vr_weapon_yawadjust && vr_weapon_yawadjust->value != 0.0f)
                out_angles[1] = anglemod(out_angles[1] + vr_weapon_yawadjust->value);
            if (vr_weapon_rolladjust && vr_weapon_rolladjust->value != 0.0f)
                out_angles[2] += vr_weapon_rolladjust->value;

            return true;
        }
        return false;
    }

    out_origin[0] = -g_xrInputState.leftHandPose.position.z;
    out_origin[1] = -g_xrInputState.leftHandPose.position.x;
    out_origin[2] = g_xrInputState.leftHandPose.position.y;

    // Two-Handed Weapon Stabiliser for left-handed primary (right hand grips barrel)
    float dx = g_xrInputState.rightHandPose.position.x - g_xrInputState.leftHandPose.position.x;
    float dy = g_xrInputState.rightHandPose.position.y - g_xrInputState.leftHandPose.position.y;
    float dz = g_xrInputState.rightHandPose.position.z - g_xrInputState.leftHandPose.position.z;
    float handDist = sqrtf(dx*dx + dy*dy + dz*dz);

    if (g_xrInputState.gripRight > 0.4f && handDist >= 0.12f && handDist <= 0.55f && g_xrInputState.rightHandActive)
    {
        vec3_t aimDir;
        aimDir[0] = (g_xrInputState.leftHandPose.position.z - g_xrInputState.rightHandPose.position.z);
        aimDir[1] = (g_xrInputState.leftHandPose.position.x - g_xrInputState.rightHandPose.position.x);
        aimDir[2] = (g_xrInputState.rightHandPose.position.y - g_xrInputState.leftHandPose.position.y);
        VectorNormalize(aimDir);
        VectorAngles(aimDir, out_angles);
    }
    else
    {
        XR_QuatToEuler( &g_xrInputState.leftHandPose.orientation, out_angles );
    }

    if (vr_weapon_pitchadjust && vr_weapon_pitchadjust->value != 0.0f)
    {
        out_angles[0] += vr_weapon_pitchadjust->value;
    }
    if (vr_weapon_yawadjust && vr_weapon_yawadjust->value != 0.0f)
    {
        out_angles[1] = anglemod(out_angles[1] + vr_weapon_yawadjust->value);
    }
    if (vr_weapon_rolladjust && vr_weapon_rolladjust->value != 0.0f)
    {
        out_angles[2] += vr_weapon_rolladjust->value;
    }

    return true;
}

qboolean XR_GetRightHandVelocity( vec3_t out_velocity )
{
    if (!g_xrSessionRunning || !g_xrInputState.rightHandActive) return false;

    // Conversão de velocidade linear para coordenadas GoldSrc:
    out_velocity[0] = -g_xrInputState.rightHandVelocity.z;
    out_velocity[1] = -g_xrInputState.rightHandVelocity.x;
    out_velocity[2] = g_xrInputState.rightHandVelocity.y;
    return true;
}

qboolean XR_GetLeftHandVelocity( vec3_t out_velocity )
{
    if (!g_xrSessionRunning || !g_xrInputState.leftHandActive) return false;

    out_velocity[0] = -g_xrInputState.leftHandVelocity.z;
    out_velocity[1] = -g_xrInputState.leftHandVelocity.x;
    out_velocity[2] = g_xrInputState.leftHandVelocity.y;
    return true;
}

qboolean XR_GetRightHandMuzzleTransform( vec3_t out_muzzle_offset, vec3_t out_aim_angles )
{
    return XR_GetPrimaryHandMuzzleTransform( out_muzzle_offset, out_aim_angles );
}

void XR_ApplyHapticFeedback( int hand, float duration_seconds, float frequency_hz, float amplitude )
{
	if( !g_xrSessionRunning || g_xrSession == XR_NULL_HANDLE )
		return;

	if( !vr_haptics_enabled || !vr_haptics_enabled->value )
		return;

	float intensity = (vr_haptics_intensity && vr_haptics_intensity->value > 0.0f) ? vr_haptics_intensity->value : 1.0f;
	amplitude *= intensity;

	if( amplitude <= 0.0f )
		return;

	if( amplitude > 1.0f )
		amplitude = 1.0f;

	if( duration_seconds <= 0.0f )
		duration_seconds = 0.02f;

	XrHapticVibration vibration = {0};
	vibration.type = XR_TYPE_HAPTIC_VIBRATION;
	vibration.duration = (XrDuration)(duration_seconds * 1000000000.0f);
	vibration.frequency = (frequency_hz > 0.0f) ? frequency_hz : XR_FREQUENCY_UNSPECIFIED;
	vibration.amplitude = amplitude;

	if(( hand == VR_HAND_LEFT || hand == VR_HAND_BOTH ) && g_actionHapticLeft != XR_NULL_HANDLE )
	{
		XrHapticActionInfo infoL = {0};
		infoL.type = XR_TYPE_HAPTIC_ACTION_INFO;
		infoL.action = g_actionHapticLeft;
		xrApplyHapticFeedback( g_xrSession, &infoL, (const XrHapticBaseHeader*)&vibration );
	}

	if(( hand == VR_HAND_RIGHT || hand == VR_HAND_BOTH ) && g_actionHapticRight != XR_NULL_HANDLE )
	{
		XrHapticActionInfo infoR = {0};
		infoR.type = XR_TYPE_HAPTIC_ACTION_INFO;
		infoR.action = g_actionHapticRight;
		xrApplyHapticFeedback( g_xrSession, &infoR, (const XrHapticBaseHeader*)&vibration );
	}
}

void XR_StopHapticFeedback( int hand )
{
	if( !g_xrSessionRunning || g_xrSession == XR_NULL_HANDLE )
		return;

	if(( hand == VR_HAND_LEFT || hand == VR_HAND_BOTH ) && g_actionHapticLeft != XR_NULL_HANDLE )
	{
		XrHapticActionInfo infoL = {0};
		infoL.type = XR_TYPE_HAPTIC_ACTION_INFO;
		infoL.action = g_actionHapticLeft;
		xrStopHapticFeedback( g_xrSession, &infoL );
	}

	if(( hand == VR_HAND_RIGHT || hand == VR_HAND_BOTH ) && g_actionHapticRight != XR_NULL_HANDLE )
	{
		XrHapticActionInfo infoR = {0};
		infoR.type = XR_TYPE_HAPTIC_ACTION_INFO;
		infoR.action = g_actionHapticRight;
		xrStopHapticFeedback( g_xrSession, &infoR );
	}
}

void XR_TriggerHapticEffect( int hand, vr_haptic_effect_t effect, float intensity_scale )
{
	int primary_hand = (vr_lefthanded && vr_lefthanded->value > 0.0f) ? VR_HAND_LEFT : VR_HAND_RIGHT;
	int offhand = (primary_hand == VR_HAND_RIGHT) ? VR_HAND_LEFT : VR_HAND_RIGHT;

	if( hand < 0 || hand > 2 )
		hand = primary_hand;

	switch( effect )
	{
	case VR_HAPTIC_WEAPON_GLOCK:
		XR_ApplyHapticFeedback( hand, 0.05f, 220.0f, 0.55f * intensity_scale );
		break;
	case VR_HAPTIC_WEAPON_PYTHON:
		XR_ApplyHapticFeedback( hand, 0.12f, 140.0f, 1.0f * intensity_scale );
		break;
	case VR_HAPTIC_WEAPON_SHOTGUN:
		XR_ApplyHapticFeedback( hand, 0.10f, 160.0f, 0.85f * intensity_scale );
		break;
	case VR_HAPTIC_WEAPON_SHOTGUN_DOUBLE:
		XR_ApplyHapticFeedback( hand, 0.18f, 120.0f, 1.0f * intensity_scale );
		XR_ApplyHapticFeedback( offhand, 0.12f, 120.0f, 0.5f * intensity_scale );
		break;
	case VR_HAPTIC_WEAPON_MP5:
		XR_ApplyHapticFeedback( hand, 0.035f, 260.0f, 0.45f * intensity_scale );
		break;
	case VR_HAPTIC_WEAPON_MP5_GRENADE:
		XR_ApplyHapticFeedback( hand, 0.14f, 130.0f, 0.9f * intensity_scale );
		break;
	case VR_HAPTIC_WEAPON_CROSSBOW:
		XR_ApplyHapticFeedback( hand, 0.06f, 280.0f, 0.5f * intensity_scale );
		break;
	case VR_HAPTIC_WEAPON_RPG:
		XR_ApplyHapticFeedback( hand, 0.22f, 110.0f, 0.95f * intensity_scale );
		XR_ApplyHapticFeedback( offhand, 0.18f, 110.0f, 0.6f * intensity_scale );
		break;
	case VR_HAPTIC_WEAPON_GAUSS:
		XR_ApplyHapticFeedback( hand, 0.08f, 300.0f, 0.75f * intensity_scale );
		break;
	case VR_HAPTIC_WEAPON_GAUSS_CHARGED:
		XR_ApplyHapticFeedback( hand, 0.25f, 180.0f, 1.0f * intensity_scale );
		XR_ApplyHapticFeedback( offhand, 0.20f, 180.0f, 0.7f * intensity_scale );
		break;
	case VR_HAPTIC_WEAPON_EGON:
		XR_ApplyHapticFeedback( hand, 0.05f, 200.0f, 0.4f * intensity_scale );
		break;
	case VR_HAPTIC_WEAPON_CROWBAR:
		XR_ApplyHapticFeedback( hand, 0.07f, 180.0f, 0.7f * intensity_scale );
		break;
	case VR_HAPTIC_WEAPON_GENERIC:
		XR_ApplyHapticFeedback( hand, 0.04f, 240.0f, 0.4f * intensity_scale );
		break;
	case VR_HAPTIC_DAMAGE_LIGHT:
		XR_ApplyHapticFeedback( VR_HAND_BOTH, 0.08f, 180.0f, 0.4f * intensity_scale );
		break;
	case VR_HAPTIC_DAMAGE_MEDIUM:
		XR_ApplyHapticFeedback( VR_HAND_BOTH, 0.15f, 150.0f, 0.7f * intensity_scale );
		break;
	case VR_HAPTIC_DAMAGE_HEAVY:
		XR_ApplyHapticFeedback( VR_HAND_BOTH, 0.25f, 120.0f, 1.0f * intensity_scale );
		break;
	case VR_HAPTIC_SUIT_CHARGE:
		XR_ApplyHapticFeedback( VR_HAND_BOTH, 0.03f, 300.0f, 0.25f * intensity_scale );
		break;
	case VR_HAPTIC_GEIGER:
		XR_ApplyHapticFeedback( VR_HAND_BOTH, 0.015f, 350.0f, 0.20f * intensity_scale );
		break;
	case VR_HAPTIC_UI_CLICK:
		XR_ApplyHapticFeedback( hand, 0.02f, 320.0f, 0.3f * intensity_scale );
		break;
	default:
		XR_ApplyHapticFeedback( hand, 0.05f, 200.0f, 0.5f * intensity_scale );
		break;
	}
}

void XR_DispatchWeaponHaptic( const char *event_name )
{
	if( !event_name || !*event_name )
		return;

	int primary_hand = (vr_lefthanded && vr_lefthanded->value > 0.0f) ? VR_HAND_LEFT : VR_HAND_RIGHT;

	if( Q_strstr( event_name, "glock" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_GLOCK, 1.0f );
	else if( Q_strstr( event_name, "python" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_PYTHON, 1.0f );
	else if( Q_strstr( event_name, "shotgun2" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_SHOTGUN_DOUBLE, 1.0f );
	else if( Q_strstr( event_name, "shotgun" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_SHOTGUN, 1.0f );
	else if( Q_strstr( event_name, "mp52" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_MP5_GRENADE, 1.0f );
	else if( Q_strstr( event_name, "mp5" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_MP5, 1.0f );
	else if( Q_strstr( event_name, "crossbow" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_CROSSBOW, 1.0f );
	else if( Q_strstr( event_name, "rpg" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_RPG, 1.0f );
	else if( Q_strstr( event_name, "gaussspin" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_GAUSS_CHARGED, 1.0f );
	else if( Q_strstr( event_name, "gauss" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_GAUSS, 1.0f );
	else if( Q_strstr( event_name, "egon" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_EGON, 1.0f );
	else if( Q_strstr( event_name, "crowbar" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_CROWBAR, 1.0f );
	else if( Q_strstr( event_name, "trip" ) || Q_strstr( event_name, "satchel" ) || Q_strstr( event_name, "snark" ))
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_GENERIC, 1.0f );
	else
		XR_TriggerHapticEffect( primary_hand, VR_HAPTIC_WEAPON_GENERIC, 1.0f );
}

static void XR_Haptic_f( void )
{
	int argc = Cmd_Argc();
	if( argc < 2 )
	{
		Con_Printf( "Usage: vr_haptic <left|right|both> [duration_sec] [freq_hz] [amplitude 0-1]\n" );
		return;
	}

	const char *target = Cmd_Argv( 1 );
	int hand = VR_HAND_RIGHT;
	if( !Q_stricmp( target, "left" ))
		hand = VR_HAND_LEFT;
	else if( !Q_stricmp( target, "both" ))
		hand = VR_HAND_BOTH;

	float dur = (argc > 2) ? Q_atof( Cmd_Argv( 2 )) : 0.1f;
	float freq = (argc > 3) ? Q_atof( Cmd_Argv( 3 )) : 160.0f;
	float amp = (argc > 4) ? Q_atof( Cmd_Argv( 4 )) : 1.0f;

	XR_ApplyHapticFeedback( hand, dur, freq, amp );
	Con_Printf( "VR Haptic triggered: hand=%s dur=%.3fs freq=%.1fHz amp=%.2f\n", target, dur, freq, amp );
}

static struct {
	qboolean active;
	qboolean hit;
	float u, v;
	int x, y;
	vec3_t rayStart;
	vec3_t rayEnd;
} s_pointerState = {0};

void XR_UpdatePointerCursor( void )
{
	if( !g_xrSessionRunning || !XR_IsActive() )
	{
		s_pointerState.active = false;
		s_pointerState.hit = false;
		return;
	}

	qboolean in_menu = (UI_IsVisible() || cls.key_dest == key_menu || cls.key_dest == key_console || cls.state == ca_disconnected);
	if( !in_menu )
	{
		XR_SetQuadHud( false );
		s_pointerState.active = false;
		s_pointerState.hit = false;
		return;
	}

	XR_SetQuadHud( true );

	if( vr_pointer_hud && vr_pointer_hud->value == 0.0f )
	{
		s_pointerState.active = false;
		return;
	}

	int hand = (vr_lefthanded && vr_lefthanded->value > 0.0f) ? VR_HAND_LEFT : VR_HAND_RIGHT;
	qboolean handActive = (hand == VR_HAND_LEFT) ? g_xrInputState.leftHandActive : g_xrInputState.rightHandActive;
	if( !handActive )
	{
		s_pointerState.active = false;
		return;
	}

	XrPosef pose = (hand == VR_HAND_LEFT) ? g_xrInputState.leftHandPose : g_xrInputState.rightHandPose;

	// Calculate pointing ray direction in OpenXR coordinates
	float qx = pose.orientation.x;
	float qy = pose.orientation.y;
	float qz = pose.orientation.z;
	float qw = pose.orientation.w;

	float dx = -2.0f * (qx * qz + qw * qy);
	float dy = -2.0f * (qy * qz - qw * qx);
	float dz = -1.0f + 2.0f * (qx * qx + qy * qy);

	float len = sqrtf( dx * dx + dy * dy + dz * dz );
	if( len > 0.0001f )
	{
		dx /= len;
		dy /= len;
		dz /= len;
	}

	// Quad plane is located at Z = -1.5m in OpenXR local space
	float planeZ = -1.5f;
	qboolean hit = false;
	float u = 0.5f, v = 0.5f;
	int px = 0, py = 0;

	float worldScale = (vr_worldscale && vr_worldscale->value > 0.0f) ? vr_worldscale->value : 40.0f;

	// Controller origin in engine units
	vec3_t rayStart, rayEnd;
	rayStart[0] = -pose.position.z * worldScale;
	rayStart[1] = -pose.position.x * worldScale;
	rayStart[2] =  pose.position.y * worldScale;

	float hit_x = pose.position.x + 2.0f * dx;
	float hit_y = pose.position.y + 2.0f * dy;
	float hit_z = pose.position.z + 2.0f * dz;

	if( dz < -0.01f )
	{
		float t = (planeZ - pose.position.z) / dz;
		if( t > 0.0f )
		{
			float ix = pose.position.x + t * dx;
			float iy = pose.position.y + t * dy;

			// Floating menu quad dimensions: 1.6m width, 0.9m height
			if( ix >= -0.8f && ix <= 0.8f && iy >= -0.45f && iy <= 0.45f )
			{
				u = (ix + 0.8f) / 1.6f;
				v = 0.5f - (iy / 0.9f);
				u = bound( 0.0f, u, 1.0f );
				v = bound( 0.0f, v, 1.0f );

				if( refState.width > 0 && refState.height > 0 )
				{
					px = bound( 0, (int)(u * (float)refState.width), refState.width - 1 );
					py = bound( 0, (int)(v * (float)refState.height), refState.height - 1 );

					UI_MouseMove( px, py );
					VGui_MouseMove( px, py );
				}

				hit = true;
				hit_x = ix;
				hit_y = iy;
				hit_z = planeZ;
			}
		}
	}

	rayEnd[0] = -hit_z * worldScale;
	rayEnd[1] = -hit_x * worldScale;
	rayEnd[2] =  hit_y * worldScale;

	s_pointerState.active = true;
	s_pointerState.hit = hit;
	s_pointerState.u = u;
	s_pointerState.v = v;
	s_pointerState.x = px;
	s_pointerState.y = py;
	VectorCopy( rayStart, s_pointerState.rayStart );
	VectorCopy( rayEnd, s_pointerState.rayEnd );

	// Dominant hand trigger click -> K_MOUSE1
	static qboolean s_prevTrigger = false;
	qboolean trigger = g_xrInputState.attack;
	if( trigger && !s_prevTrigger )
	{
		s_prevTrigger = true;
		if( hit )
		{
			XR_TriggerHapticEffect( hand, VR_HAPTIC_UI_CLICK, 0.6f );
			Key_Event( K_MOUSE1, true );
		}
	}
	else if( !trigger && s_prevTrigger )
	{
		s_prevTrigger = false;
		Key_Event( K_MOUSE1, false );
	}

	// Dominant hand secondary button -> K_ESCAPE
	static qboolean s_prevBack = false;
	qboolean back = g_xrInputState.attack2;
	if( back && !s_prevBack )
	{
		s_prevBack = true;
		XR_TriggerHapticEffect( hand, VR_HAPTIC_UI_CLICK, 0.4f );
		Key_Event( K_ESCAPE, true );
	}
	else if( !back && s_prevBack )
	{
		s_prevBack = false;
		Key_Event( K_ESCAPE, false );
	}

	// Analog thumbstick scroll
	static double s_nextScrollTime = 0.0;
	if( host.realtime >= s_nextScrollTime )
	{
		if( g_xrInputState.turnY > 0.4f )
		{
			IN_MWheelEvent( 1 );
			s_nextScrollTime = host.realtime + 0.15;
		}
		else if( g_xrInputState.turnY < -0.4f )
		{
			IN_MWheelEvent( -1 );
			s_nextScrollTime = host.realtime + 0.15;
		}
	}
}

qboolean XR_GetPointerLaserRay( vec3_t out_start, vec3_t out_end, qboolean *out_hit, float *out_u, float *out_v )
{
	if( !s_pointerState.active )
		return false;

	if( out_start ) VectorCopy( s_pointerState.rayStart, out_start );
	if( out_end ) VectorCopy( s_pointerState.rayEnd, out_end );
	if( out_hit ) *out_hit = s_pointerState.hit;
	if( out_u ) *out_u = s_pointerState.u;
	if( out_v ) *out_v = s_pointerState.v;
	return true;
}

qboolean XR_GetPointerCursorPos( int *out_x, int *out_y, qboolean *out_hit )
{
	if( !s_pointerState.active )
		return false;

	if( out_x ) *out_x = s_pointerState.x;
	if( out_y ) *out_y = s_pointerState.y;
	if( out_hit ) *out_hit = s_pointerState.hit;
	return true;
}

#endif // XASH_OPENXR
