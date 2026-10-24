#include "common.h"
#include "xr_input.h"
#include "xr_core.h"
#include "xr_swapchain.h"
#include "xr_profile.h"
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
static XrAction g_actionJumpLeft = XR_NULL_HANDLE;
static XrAction g_actionDuck = XR_NULL_HANDLE;
static XrAction g_actionUse = XR_NULL_HANDLE;
static XrAction g_actionReload = XR_NULL_HANDLE;
static XrAction g_actionReloadLeft = XR_NULL_HANDLE;
static XrAction g_actionAltFire = XR_NULL_HANDLE;
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

// Extract action creation into a dedicated initialization helper
static void XR_CreateAllActions( void )
{
    g_actionAttack      = CreateAction("attack", "Attack", XR_ACTION_TYPE_FLOAT_INPUT);
    g_actionAttack2     = CreateAction("attack2", "Secondary Attack", XR_ACTION_TYPE_FLOAT_INPUT);
    g_actionGripLeft    = CreateAction("grip_left", "Left Hand Grip", XR_ACTION_TYPE_FLOAT_INPUT);
    g_actionGripRight   = CreateAction("grip_right", "Right Hand Grip", XR_ACTION_TYPE_FLOAT_INPUT);
    g_actionJump        = CreateAction("jump", "Jump", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionJumpLeft    = CreateAction("jump_left", "Jump (Left Handed)", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionDuck        = CreateAction("duck", "Crouch", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionUse         = CreateAction("use", "Use / Interact", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionReload      = CreateAction("reload", "Reload", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionReloadLeft  = CreateAction("reload_left", "Reload (Left Handed)", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionAltFire     = CreateAction("altfire", "Secondary Fire / Alt-Fire", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionFlashlight  = CreateAction("flashlight", "Flashlight (impulse 100)", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionMenu        = CreateAction("menu_toggle", "Menu / Pause", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionSprint      = CreateAction("sprint", "Sprint", XR_ACTION_TYPE_BOOLEAN_INPUT);
    g_actionMove        = CreateAction("move", "Move (Locomotion)", XR_ACTION_TYPE_VECTOR2F_INPUT);
    g_actionTurn        = CreateAction("turn", "Turn (Snap/Smooth)", XR_ACTION_TYPE_VECTOR2F_INPUT);
    g_actionAimPoseLeft = CreateAction("aim_left", "Left Aim Pose", XR_ACTION_TYPE_POSE_INPUT);
    g_actionAimPoseRight= CreateAction("aim_right", "Right Aim Pose", XR_ACTION_TYPE_POSE_INPUT);
    g_actionHapticLeft  = CreateAction("haptic_left", "Left Hand Haptics", XR_ACTION_TYPE_VIBRATION_OUTPUT);
    g_actionHapticRight = CreateAction("haptic_right", "Right Hand Haptics", XR_ACTION_TYPE_VIBRATION_OUTPUT);
}

// Extract interaction profile bindings into a dedicated helper
static void XR_SuggestAllBindings( void )
{
    // Map Oculus / Meta Quest Touch Controller profile (HL2:VR standard layout)
    XrPath oculusProfile = StringToPath("/interaction_profiles/oculus/touch_controller");
    XrActionSuggestedBinding oculusBindings[] = {
        { g_actionAttack,       StringToPath("/user/hand/right/input/trigger/value") },
        { g_actionAttack2,      StringToPath("/user/hand/left/input/trigger/value") },
        { g_actionGripRight,    StringToPath("/user/hand/right/input/squeeze/value") },
        { g_actionGripLeft,     StringToPath("/user/hand/left/input/squeeze/value") },
        { g_actionJump,         StringToPath("/user/hand/right/input/a/click") },           // Right A = Jump
        { g_actionReload,       StringToPath("/user/hand/right/input/b/click") },           // Right B = Reload / Eject
        { g_actionJumpLeft,     StringToPath("/user/hand/left/input/x/click") },            // Left X = Jump (left-handed)
        { g_actionReloadLeft,   StringToPath("/user/hand/left/input/y/click") },            // Left Y = Reload (left-handed)
        { g_actionDuck,         StringToPath("/user/hand/right/input/thumbstick/click") },  // Right Stick Click = Crouch
        { g_actionSprint,       StringToPath("/user/hand/left/input/thumbstick/click") },   // Left Stick Click = Sprint
        { g_actionMenu,         StringToPath("/user/hand/left/input/menu/click") },        // HL2:VR: Left Menu = Pause / Menu
        { g_actionMove,         StringToPath("/user/hand/left/input/thumbstick") },        // Locomotion (Move)
        { g_actionTurn,         StringToPath("/user/hand/right/input/thumbstick") },       // Turning (Snap/Smooth)
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

    // Map Valve Index Controller profile (HL2:VR standard layout)
    XrPath indexProfile = StringToPath("/interaction_profiles/valve/index_controller");
    XrActionSuggestedBinding indexBindings[] = {
        { g_actionAttack,       StringToPath("/user/hand/right/input/trigger/value") },
        { g_actionAttack2,      StringToPath("/user/hand/left/input/trigger/value") },
        { g_actionGripRight,    StringToPath("/user/hand/right/input/squeeze/value") },
        { g_actionGripLeft,     StringToPath("/user/hand/left/input/squeeze/value") },
        { g_actionJump,         StringToPath("/user/hand/right/input/a/click") },           // Index Right A = Jump
        { g_actionReload,       StringToPath("/user/hand/right/input/b/click") },           // Index Right B = Reload
        { g_actionJumpLeft,     StringToPath("/user/hand/left/input/a/click") },            // Index Left A = Jump (left-handed)
        { g_actionReloadLeft,   StringToPath("/user/hand/left/input/b/click") },            // Index Left B = Reload (left-handed)
        { g_actionDuck,         StringToPath("/user/hand/right/input/thumbstick/click") },  // Index Right Stick Click = Crouch
        { g_actionSprint,       StringToPath("/user/hand/left/input/thumbstick/click") },   // Index Left Stick Click = Sprint
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
}

// Extract session attachment and action spaces creation
static qboolean XR_AttachActionSetsAndSpaces( void )
{
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

    XrActionSpaceCreateInfo spaceInfo = {0};
    spaceInfo.type = XR_TYPE_ACTION_SPACE_CREATE_INFO;
    spaceInfo.poseInActionSpace.orientation.w = 1.0f;

    spaceInfo.action = g_actionAimPoseLeft;
    xrCreateActionSpace(g_xrSession, &spaceInfo, &g_leftHandSpace);

    spaceInfo.action = g_actionAimPoseRight;
    xrCreateActionSpace(g_xrSession, &spaceInfo, &g_rightHandSpace);

    return true;
}

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

    XR_CreateAllActions();
    XR_SuggestAllBindings();

    if (!XR_AttachActionSetsAndSpaces())
    {
        return false;
    }

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
    g_actionJumpLeft = XR_NULL_HANDLE;
    g_actionDuck = XR_NULL_HANDLE;
    g_actionUse = XR_NULL_HANDLE;
    g_actionReload = XR_NULL_HANDLE;
    g_actionReloadLeft = XR_NULL_HANDLE;
    g_actionAltFire = XR_NULL_HANDLE;
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

// Read analog triggers, grips, and digital action states
static void XR_SyncActionStates( void )
{
    XrActionStateGetInfo getInfo = {0};
    getInfo.type = XR_TYPE_ACTION_STATE_GET_INFO;

    XrActionStateFloat floatState = {0};
    floatState.type = XR_TYPE_ACTION_STATE_FLOAT;

    getInfo.action = g_actionAttack;
    if (XR_SUCCEEDED(xrGetActionStateFloat(g_xrSession, &getInfo, &floatState)))
    {
        g_xrInputState.triggerRight = floatState.currentState;
        g_xrInputState.attack = (floatState.currentState > 0.5f);
    }

    getInfo.action = g_actionAttack2;
    if (XR_SUCCEEDED(xrGetActionStateFloat(g_xrSession, &getInfo, &floatState)))
    {
        g_xrInputState.triggerLeft = floatState.currentState;
        g_xrInputState.attack2 = (floatState.currentState > 0.5f);
    }

    if (g_actionGripRight != XR_NULL_HANDLE)
    {
        getInfo.action = g_actionGripRight;
        if (XR_SUCCEEDED(xrGetActionStateFloat(g_xrSession, &getInfo, &floatState)))
        {
            g_xrInputState.gripRight = floatState.currentState;
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

    // Read digital action states
    XrActionStateBoolean boolState = {0};
    boolState.type = XR_TYPE_ACTION_STATE_BOOLEAN;

    getInfo.action = g_actionJump;
    if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
        g_xrInputState.jump = boolState.currentState;

    getInfo.action = g_actionJumpLeft;
    if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
        g_xrInputState.jumpLeft = boolState.currentState;

    getInfo.action = g_actionDuck;
    if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
        g_xrInputState.duck = boolState.currentState;

    getInfo.action = g_actionUse;
    if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
        g_xrInputState.use = boolState.currentState;

    getInfo.action = g_actionReload;
    if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
        g_xrInputState.reload = boolState.currentState;

    getInfo.action = g_actionReloadLeft;
    if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
        g_xrInputState.reloadLeft = boolState.currentState;

    if (g_actionAltFire != XR_NULL_HANDLE)
    {
        getInfo.action = g_actionAltFire;
        if (XR_SUCCEEDED(xrGetActionStateBoolean(g_xrSession, &getInfo, &boolState)))
            g_xrInputState.altfire = boolState.currentState;
    }

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

    // Simulated button inputs for automated regression testing
    if (vr_test_btn_reload && vr_test_btn_reload->value > 0.0f)
        g_xrInputState.reload = true;
    if (vr_test_btn_altfire && vr_test_btn_altfire->value > 0.0f)
    {
        // Simulate the main-hand grip+trigger combination.
        g_xrInputState.attack = true;
        if (vr_lefthanded && vr_lefthanded->value > 0.0f)
            g_xrInputState.gripLeft = 1.0f;
        else
            g_xrInputState.gripRight = 1.0f;
    }
    if (vr_test_btn_jump && vr_test_btn_jump->value > 0.0f)
        g_xrInputState.jump = true;
    if (vr_test_btn_reload_left && vr_test_btn_reload_left->value > 0.0f)
        g_xrInputState.reloadLeft = true;
    if (vr_test_btn_jump_left && vr_test_btn_jump_left->value > 0.0f)
        g_xrInputState.jumpLeft = true;
    if (vr_test_btn_menu && vr_test_btn_menu->value > 0.0f)
        g_xrInputState.menu = true;
    if (vr_test_offhand_grip && vr_test_offhand_grip->value > 0.0f)
    {
        g_xrInputState.gripLeft = 1.0f;
        g_xrInputState.gripRight = 1.0f;
    }
}

// Read analog thumbsticks and compute procedural finger curling heuristics
static void XR_SyncThumbsticksAndCurls( void )
{
    XrActionStateGetInfo getInfo = {0};
    getInfo.type = XR_TYPE_ACTION_STATE_GET_INFO;

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

    // Procedural thumb curling heuristic based on buttons and thumbstick touches/deflections
    qboolean lefthanded = (vr_lefthanded && vr_lefthanded->value > 0.0f);
    qboolean rightThumbActive = lefthanded ?
        (g_xrInputState.jump || g_xrInputState.use || g_xrInputState.sprint ||
         fabsf(g_xrInputState.moveX) > 0.05f || fabsf(g_xrInputState.moveY) > 0.05f) :
        (g_xrInputState.reload || g_xrInputState.altfire || g_xrInputState.duck ||
         fabsf(g_xrInputState.turnX) > 0.05f || fabsf(g_xrInputState.turnY) > 0.05f);
    float targetThumbRight = rightThumbActive ? 1.0f : 0.0f;

    qboolean leftThumbActive = lefthanded ?
        (g_xrInputState.reload || g_xrInputState.altfire || g_xrInputState.duck ||
         fabsf(g_xrInputState.turnX) > 0.05f || fabsf(g_xrInputState.turnY) > 0.05f) :
        (g_xrInputState.jump || g_xrInputState.use || g_xrInputState.sprint || g_xrInputState.menu ||
         fabsf(g_xrInputState.moveX) > 0.05f || fabsf(g_xrInputState.moveY) > 0.05f);
    float targetThumbLeft = leftThumbActive ? 1.0f : 0.0f;

    // Smooth response (~100ms) to avoid instantaneous finger snapping
    float curlLerp = 0.25f;
    g_xrInputState.thumbRight += (targetThumbRight - g_xrInputState.thumbRight) * curlLerp;
    g_xrInputState.thumbLeft  += (targetThumbLeft  - g_xrInputState.thumbLeft) * curlLerp;

    // Simulated finger curling axes for headless regression testing
    if (vr_test_finger_curl && vr_test_finger_curl->value > 0.0f)
    {
        g_xrInputState.triggerRight = 0.85f;
        g_xrInputState.triggerLeft  = 0.75f;
        g_xrInputState.gripRight    = 0.90f;
        g_xrInputState.gripLeft     = 0.60f;
        g_xrInputState.thumbRight   = 0.80f;
        g_xrInputState.thumbLeft    = 0.70f;
    }
}

// Locate left and right hand tracking spaces and record velocities (6DoF)
static void XR_SyncHandPoses( XrTime syncTime )
{
    if (syncTime <= 0) return;

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

    XR_SyncActionStates();
    XR_SyncThumbsticksAndCurls();
    XR_SyncHandPoses(XR_GetPredictedDisplayTime());
}

// Primary trigger = fire. Grip + trigger on the primary hand = alt-fire.
// The off-hand trigger is reserved for use/interact and must never alt-fire.
static void XR_ProcessTriggers( usercmd_t *cmd, float gripDominant, qboolean attackDominant )
{
    static qboolean s_prevAltFireCombo = false;

    if (attackDominant)
    {
        if (gripDominant > 0.5f)
        {
            cmd->buttons |= IN_ATTACK2;

            if (!s_prevAltFireCombo)
                Con_Printf("^2[VR_INPUT] Main hand grip+trigger alt-fire\n");

            s_prevAltFireCombo = true;
        }
        else
        {
            cmd->buttons |= IN_ATTACK;
            s_prevAltFireCombo = false;
        }
    }
    else
    {
        s_prevAltFireCombo = false;
    }
}

// Process physical roomscale squat ducking and stick sprint/crouch
static void XR_ProcessCrouchAndSprint( usercmd_t *cmd, qboolean stickCrouch, qboolean stickSprint )
{
    qboolean physicalCrouch = false;
    if (vr_physical_crouch && vr_physical_crouch->value > 0.0f)
    {
        float headDrop = XR_GetRoomscaleHeadDrop();
        if (headDrop < -0.28f)
            physicalCrouch = true;
    }

    static qboolean s_prevPhysicalCrouch = false;
    if (physicalCrouch && !s_prevPhysicalCrouch)
    {
        Con_Printf("^2[VR_INPUT] Physical Roomscale Crouch ENGAGED (headDrop=%.2fm) -> IN_DUCK hull 36\n", XR_GetRoomscaleHeadDrop());
    }
    else if (!physicalCrouch && s_prevPhysicalCrouch)
    {
        Con_Printf("^2[VR_INPUT] Physical Roomscale Crouch RELEASED -> standing hull 72\n");
    }
    s_prevPhysicalCrouch = physicalCrouch;

    if (stickCrouch || physicalCrouch) cmd->buttons |= IN_DUCK;
    if (stickSprint) cmd->buttons |= IN_RUN;
}

// Process VR button mappings (fire/alt-fire, reload, jump, crouch, sprint)
static void XR_ProcessButtonInputs( usercmd_t *cmd, qboolean lefthanded,
                                    float gripDominant, qboolean attackDominant,
                                    qboolean btnReload, qboolean btnJump,
                                    qboolean stickCrouch, qboolean stickSprint )
{
    XR_ProcessTriggers( cmd, gripDominant, attackDominant );

    // Right B (or Left Y in left-handed mode): reload / eject
    static qboolean s_prevReload = false;
    if (btnReload) cmd->buttons |= IN_RELOAD;
    if (btnReload && !s_prevReload)
    {
        Con_Printf("^2[VR_INPUT] HL2VR Action: Reload triggered (%s)\n",
            lefthanded ? "Left Y" : "Right B");
    }
    s_prevReload = btnReload;

    // Right A (or Left X in left-handed mode): jump
    static qboolean s_prevJump = false;
    if (btnJump) cmd->buttons |= IN_JUMP;
    if (btnJump && !s_prevJump)
    {
        Con_Printf("^2[VR_INPUT] HL2VR Action: Jump triggered (%s)\n",
            lefthanded ? "Left X" : "Right A");
    }
    s_prevJump = btnJump;

    XR_ProcessCrouchAndSprint( cmd, stickCrouch, stickSprint );
}

// Compute hand position relative to head view space for gesture detection
static qboolean XR_GetHandPositionInHeadView( int hand, XrTime syncTime, XrVector3f *out_pos )
{
    XrSpace handSpace = (hand == VR_HAND_LEFT) ? g_leftHandSpace : g_rightHandSpace;

    // Automated test override for headless / simulated validation
    if (vr_test_headgesture && vr_test_headgesture->value > 0.0f)
    {
        if (((int)vr_test_headgesture->value == 1 && hand == VR_HAND_RIGHT) ||
            ((int)vr_test_headgesture->value == 2 && hand == VR_HAND_LEFT))
        {
            out_pos->x = (hand == VR_HAND_RIGHT) ? 0.16f : -0.16f;
            out_pos->y = 0.02f;
            out_pos->z = 0.05f;
            return true;
        }
        return false;
    }

    if (handSpace != XR_NULL_HANDLE && g_xrViewSpace != XR_NULL_HANDLE && syncTime > 0)
    {
        XrSpaceLocation loc = {0};
        loc.type = XR_TYPE_SPACE_LOCATION;
        if (XR_SUCCEEDED(xrLocateSpace(handSpace, g_xrViewSpace, syncTime, &loc)))
        {
            if (loc.locationFlags & XR_SPACE_LOCATION_POSITION_VALID_BIT)
            {
                *out_pos = loc.pose.position;
                return true;
            }
        }
    }

    // Fallback: transform local-space hand pose to head view coordinates
    const XrPosef *handPose = (hand == VR_HAND_LEFT) ? &g_xrInputState.leftHandPose : &g_xrInputState.rightHandPose;
    qboolean handActive = (hand == VR_HAND_LEFT) ? g_xrInputState.leftHandActive : g_xrInputState.rightHandActive;
    if (handActive)
    {
        float dx = handPose->position.x - g_xrViews[0].pose.position.x;
        float dy = handPose->position.y - g_xrViews[0].pose.position.y;
        float dz = handPose->position.z - g_xrViews[0].pose.position.z;

        float qx = g_xrViews[0].pose.orientation.x;
        float qy = g_xrViews[0].pose.orientation.y;
        float qz = g_xrViews[0].pose.orientation.z;
        float qw = g_xrViews[0].pose.orientation.w;

        // Rotate by conjugate of head orientation: q_inv = (-qx, -qy, -qz, qw)
        float t2 =   qw * dx + qy * dz - qz * dy;
        float t3 =   qw * dy + qz * dx - qx * dz;
        float t4 =   qw * dz + qx * dy - qy * dx;
        float t1 =  -qx * dx - qy * dy - qz * dz;
        out_pos->x = t2 * qw - t1 * qx - t3 * qz + t4 * qy;
        out_pos->y = t3 * qw - t1 * qy - t4 * qx + t2 * qz;
        out_pos->z = t4 * qw - t1 * qz - t2 * qy + t3 * qx;
        return true;
    }

    return false;
}

// Head-Click Flashlight Gesture (HL2:VR style): temple click toggles head flashlight
static void XR_ProcessHeadFlashlightGesture( usercmd_t *cmd, qboolean lefthanded )
{
    qboolean headGestureTriggered = false;
    static qboolean s_headGestureDebounced = false;
    static double s_nextHeadGestureTime = 0.0;
    XrTime gestureSyncTime = XR_GetPredictedDisplayTime();

    for (int h = 0; h < 2; h++)
    {
        XrVector3f posInView = {0};
        if (!XR_GetHandPositionInHeadView(h, gestureSyncTime, &posInView))
            continue;

        float dist = sqrtf(posInView.x * posInView.x + posInView.y * posInView.y + posInView.z * posInView.z);
        // Ear/temple region:
        // 1. Distance to head center < 0.28m
        // 2. Lateral offset |x| > 0.07m (at the side of head, not in front of face)
        // 3. Vertical level |y| < 0.18m (eye/ear level)
        // 4. Longitudinal range -0.15m <= z <= 0.22m
        qboolean inTempleRegion = (dist < 0.28f && fabsf(posInView.x) > 0.07f &&
                                   fabsf(posInView.y) < 0.18f &&
                                   posInView.z > -0.15f && posInView.z < 0.22f);

        if (inTempleRegion)
        {
            qboolean handClicked = false;
            if (h == VR_HAND_RIGHT)
            {
                handClicked = g_xrInputState.attack;
                if (vr_test_click && vr_test_click->value > 0.0f)
                    handClicked = true;
            }
            else
            {
                handClicked = g_xrInputState.attack2;
                if (vr_test_click && vr_test_click->value == 2.0f)
                    handClicked = true;
            }

            if (handClicked)
            {
                // Suppress weapon firing to avoid accidental discharge when reaching for head
                cmd->buttons &= ~(IN_ATTACK | IN_ATTACK2);

                if (!s_headGestureDebounced && host.realtime >= s_nextHeadGestureTime)
                {
                    s_headGestureDebounced = true;
                    s_nextHeadGestureTime = host.realtime + 0.35;
                    headGestureTriggered = true;

                    Cbuf_AddText("impulse 100\n");
                    XR_TriggerHapticEffect(h, VR_HAPTIC_UI_CLICK, 0.7f);
                    Con_Printf("^2[VR_GESTURE] Head flashlight toggled by %s hand gesture! (dist=%.2fm, x=%.2fm, y=%.2fm, z=%.2fm)\n",
                        (h == VR_HAND_LEFT) ? "LEFT" : "RIGHT", dist, posInView.x, posInView.y, posInView.z);
                }
            }
        }
    }

    if (!headGestureTriggered)
    {
        qboolean anyClickHeld = (g_xrInputState.attack || g_xrInputState.attack2 ||
                                 g_xrInputState.gripLeft > 0.5f || g_xrInputState.gripRight > 0.5f);
        if (!anyClickHeld && (vr_test_click == NULL || vr_test_click->value == 0.0f))
        {
            s_headGestureDebounced = false;
        }
    }
}

// Weapon selection gestures (thumbstick flick for cycle, backpack gesture for crowbar)
static void XR_ProcessWeaponSelectionGestures( usercmd_t *cmd, qboolean lefthanded, float rawTurnY, qboolean attackDominant )
{
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

    // Backpack Gesture: reaching behind shoulder saca pé de cabra
    static qboolean backpack_debounced = false;
    XrPosef dominantPose = lefthanded ? g_xrInputState.leftHandPose : g_xrInputState.rightHandPose;
    if (dominantPose.position.z > 0.10f && dominantPose.position.y > -0.15f)
    {
        if (attackDominant && !backpack_debounced)
        {
            Cbuf_AddText("slot1\n"); // Draw Crowbar!
            XR_TriggerHapticEffect(lefthanded ? VR_HAND_LEFT : VR_HAND_RIGHT, VR_HAPTIC_WEAPON_CROWBAR, 0.7f);
            backpack_debounced = true;
        }
    }
    else
    {
        backpack_debounced = false;
    }
}

// Touch-to-Use Gesture: extending the off-hand near an object and pulling the
// off-hand trigger activates +use. The reach test is only an arming condition;
// the trigger is required so the hand never activates things by accident.
static void XR_ProcessTouchToUse( usercmd_t *cmd, qboolean lefthanded, qboolean offhandTrigger )
{
    static qboolean s_touchUseActive = false;
    if (!vr_gesture_use || vr_gesture_use->value <= 0.0f)
    {
        s_touchUseActive = false;
        return;
    }

    const XrPosef *offhandPose = lefthanded ? &g_xrInputState.rightHandPose : &g_xrInputState.leftHandPose;
    qboolean offhandActive = lefthanded ? g_xrInputState.rightHandActive : g_xrInputState.leftHandActive;

    if (offhandActive && !XR_IsTwoHandStabilized())
    {
        float dx = offhandPose->position.x - g_xrViews[0].pose.position.x;
        float dy = offhandPose->position.y - g_xrViews[0].pose.position.y;
        float dz = offhandPose->position.z - g_xrViews[0].pose.position.z;

        // Rotate relative vector by head yaw to determine true forward reach in player reference frame
        vec3_t headAngles;
        XR_GetHeadOrientation(headAngles);
        float yaw_rad = DEG2RAD(headAngles[1]);
        float fwdReach = -(dx * sinf(yaw_rad) + dz * cosf(yaw_rad));
        float latReach = fabsf(dx * cosf(yaw_rad) - dz * sinf(yaw_rad));

        // Forward reach > 0.40m with hysteresis
        if (!s_touchUseActive && fwdReach > 0.40f && latReach < 0.32f && fabsf(dy) < 0.30f)
        {
            s_touchUseActive = true;
        }
        else if (s_touchUseActive && (fwdReach < 0.32f || latReach > 0.40f))
        {
            s_touchUseActive = false;
        }

        // Sprint B will aim a dedicated server-side use trace from the
        // off-hand; for now the engine's standard IN_USE ray is used.
        if (s_touchUseActive && offhandTrigger)
        {
            cmd->buttons |= IN_USE;
        }
    }
    else
    {
        s_touchUseActive = false;
    }
}

// Proximity Scope: bringing weapon near headset activates optical zoom (+attack2)
static void XR_ProcessProximityScope( usercmd_t *cmd, qboolean lefthanded )
{
    static qboolean s_proximityScopeEngaged = false;
    static double s_nextScopeTime = 0.0;
    if (!vr_proximity_scope || vr_proximity_scope->value <= 0.0f) return;

    const XrPosef *primaryPose = lefthanded ? &g_xrInputState.leftHandPose : &g_xrInputState.rightHandPose;
    qboolean primaryActive = lefthanded ? g_xrInputState.leftHandActive : g_xrInputState.rightHandActive;

    if (!primaryActive) return;

    float rx = primaryPose->position.x - g_xrViews[0].pose.position.x;
    float ry = primaryPose->position.y - g_xrViews[0].pose.position.y;
    float rz = primaryPose->position.z - g_xrViews[0].pose.position.z;
    float eyeDist = sqrtf(rx*rx + ry*ry + rz*rz);

    // Allow scope for designated long-range weapons (Crossbow, Magnum) or stabilized hold
    qboolean is_scoped_weapon = (clgame.viewent.model && (Q_stristr(clgame.viewent.model->name, "crossbow") || Q_stristr(clgame.viewent.model->name, "357")));
    qboolean scopeReady = (XR_IsTwoHandStabilized() || (vr_twohanded && vr_twohanded->value == 0.0f) || is_scoped_weapon);

    // Ergonomic proximity threshold: 24cm engagement, 32cm release (prevents controller from colliding with headset)
    if (!s_proximityScopeEngaged && scopeReady && eyeDist < 0.24f && host.realtime >= s_nextScopeTime)
    {
        s_proximityScopeEngaged = true;
        s_nextScopeTime = host.realtime + 0.35;
        cmd->buttons |= IN_ATTACK2;
        XR_TriggerHapticEffect(lefthanded ? VR_HAND_LEFT : VR_HAND_RIGHT, VR_HAPTIC_UI_CLICK, 0.4f);
    }
    else if (s_proximityScopeEngaged && (eyeDist > 0.32f || !scopeReady) && host.realtime >= s_nextScopeTime)
    {
        s_proximityScopeEngaged = false;
        s_nextScopeTime = host.realtime + 0.35;
        cmd->buttons |= IN_ATTACK2;
    }
}

// Crowbar physical melee swing detector (velocity > 48 units/s)
static void XR_ProcessPhysicalMeleeSwing( usercmd_t *cmd, qboolean lefthanded )
{
    static double s_nextCrowbarSwingTime = 0.0;
    if (!vr_melee_swing || vr_melee_swing->value <= 0.0f || host.realtime < s_nextCrowbarSwingTime)
        return;

    vec3_t primaryVel;
    if (XR_GetPrimaryHandVelocity(primaryVel))
    {
        float speed = VectorLength(primaryVel);
        float worldScale = (vr_worldscale && vr_worldscale->value > 0.0f) ? vr_worldscale->value : 40.0f;
        float speedInUnits = speed * worldScale; // Convert metric m/s to GoldSrc coordinate units/s

        // 1.2 m/s * 40 units/m = 48 units/s threshold
        if (speedInUnits > 48.0f || speed > 1.20f)
        {
            if (clgame.viewent.model && strstr(clgame.viewent.model->name, "crowbar"))
            {
                cmd->buttons |= IN_ATTACK;
                s_nextCrowbarSwingTime = host.realtime + 0.30;
                XR_TriggerHapticEffect(lefthanded ? VR_HAND_LEFT : VR_HAND_RIGHT, VR_HAPTIC_WEAPON_CROWBAR, 0.75f);
            }
        }
    }
}

// Real-time 6DoF weapon offset and angle calibration using controller thumbsticks (Team Beef / Lambda1VR PR #2339).
// Allows fine-tuning weapon grip offsets (forward, right, up) and barrel alignment
// (pitch, yaw, roll) live in VR with haptic click feedback and on-screen HUD status.
// Activated cleanly via the in-headset VR menu (CMenuVR) or launcher without accidental button triggers.
static qboolean XR_ProcessThumbstickCalibration( usercmd_t *cmd, qboolean lefthanded, float *pTurnX, float *pTurnY )
{
    if (!vr_calibration_stick || vr_calibration_stick->value <= 0.0f)
        return false;

    static int s_activeCalibAxis = 0;
    static qboolean s_calibAxisDebounced = false;
    static qboolean s_calibValueDebounced = false;
    static double s_nextCalibRepeatTime = 0.0;

    static const struct {
        convar_t **cvar;
        const char *name;
        float step;
    } s_calibAxes[] = {
        { &vr_weapon_offset_forward, "Forward Offset", 0.5f },
        { &vr_weapon_offset_right,   "Right Offset",   0.5f },
        { &vr_weapon_offset_up,      "Up Offset",      0.5f },
        { &vr_weapon_pitchadjust,    "Pitch Adjust",   0.5f },
        { &vr_weapon_yawadjust,      "Yaw Adjust",     0.5f },
        { &vr_weapon_rolladjust,     "Roll Adjust",    0.5f }
    };
    const int numAxes = (int)(sizeof(s_calibAxes) / sizeof(s_calibAxes[0]));

    float rawX = *pTurnX;
    float rawY = *pTurnY;

    // Axis selection via stick Left / Right
    if (rawX > 0.5f)
    {
        if (!s_calibAxisDebounced)
        {
            s_activeCalibAxis = (s_activeCalibAxis + 1) % numAxes;
            s_calibAxisDebounced = true;
            XR_TriggerHapticEffect(lefthanded ? VR_HAND_LEFT : VR_HAND_RIGHT, VR_HAPTIC_UI_CLICK, 0.4f);
        }
    }
    else if (rawX < -0.5f)
    {
        if (!s_calibAxisDebounced)
        {
            s_activeCalibAxis = (s_activeCalibAxis + numAxes - 1) % numAxes;
            s_calibAxisDebounced = true;
            XR_TriggerHapticEffect(lefthanded ? VR_HAND_LEFT : VR_HAND_RIGHT, VR_HAPTIC_UI_CLICK, 0.4f);
        }
    }
    else if (fabsf(rawX) < 0.2f)
    {
        s_calibAxisDebounced = false;
    }

    // Value adjustment via stick Up / Down
    if (rawY > 0.5f)
    {
        if (!s_calibValueDebounced || host.realtime >= s_nextCalibRepeatTime)
        {
            convar_t *var = *s_calibAxes[s_activeCalibAxis].cvar;
            if (var)
            {
                float newVal = roundf((var->value + s_calibAxes[s_activeCalibAxis].step) * 10.0f) / 10.0f;
                Cvar_DirectSetValue(var, newVal);
            }
            XR_TriggerHapticEffect(lefthanded ? VR_HAND_LEFT : VR_HAND_RIGHT, VR_HAPTIC_UI_CLICK, 0.5f);
            if (!s_calibValueDebounced)
            {
                s_calibValueDebounced = true;
                s_nextCalibRepeatTime = host.realtime + 0.35;
            }
            else
            {
                s_nextCalibRepeatTime = host.realtime + 0.12;
            }
        }
    }
    else if (rawY < -0.5f)
    {
        if (!s_calibValueDebounced || host.realtime >= s_nextCalibRepeatTime)
        {
            convar_t *var = *s_calibAxes[s_activeCalibAxis].cvar;
            if (var)
            {
                float newVal = roundf((var->value - s_calibAxes[s_activeCalibAxis].step) * 10.0f) / 10.0f;
                Cvar_DirectSetValue(var, newVal);
            }
            XR_TriggerHapticEffect(lefthanded ? VR_HAND_LEFT : VR_HAND_RIGHT, VR_HAPTIC_UI_CLICK, 0.5f);
            if (!s_calibValueDebounced)
            {
                s_calibValueDebounced = true;
                s_nextCalibRepeatTime = host.realtime + 0.35;
            }
            else
            {
                s_nextCalibRepeatTime = host.realtime + 0.12;
            }
        }
    }
    else if (fabsf(rawY) < 0.2f)
    {
        s_calibValueDebounced = false;
    }

    // On-screen HUD notification
    convar_t *curVar = *s_calibAxes[s_activeCalibAxis].cvar;
    float curVal = curVar ? curVar->value : 0.0f;
    Con_NPrintf(0, "^2=== VR 6DOF WEAPON CALIBRATION MODE === (VR Menu to exit)");
    Con_NPrintf(1, "^3>> Selected Axis: [%s] = %.1f <<", s_calibAxes[s_activeCalibAxis].name, curVal);
    Con_NPrintf(2, "^7Flick Stick L/R: Change Axis | Stick U/D: Adjust (+/- 0.5)");
    Con_NPrintf(3, "^7Offsets: Fwd: %.1f | Rt: %.1f | Up: %.1f",
        vr_weapon_offset_forward ? vr_weapon_offset_forward->value : 0.0f,
        vr_weapon_offset_right ? vr_weapon_offset_right->value : 0.0f,
        vr_weapon_offset_up ? vr_weapon_offset_up->value : 0.0f);
    Con_NPrintf(4, "^7Angles:  Pitch: %.1f | Yaw: %.1f | Roll: %.1f",
        vr_weapon_pitchadjust ? vr_weapon_pitchadjust->value : 0.0f,
        vr_weapon_yawadjust ? vr_weapon_yawadjust->value : 0.0f,
        vr_weapon_rolladjust ? vr_weapon_rolladjust->value : 0.0f);

    // Consume stick inputs so that turning and weapon switching gestures are suppressed while calibrating
    *pTurnX = 0.0f;
    *pTurnY = 0.0f;

    return true;
}

// Locomotion and turning calculation (snap / smooth turning and decouple movement)
static void XR_ProcessLocomotionAndTurn( usercmd_t *cmd, float frametime, float rawMoveX, float rawMoveY, float rawTurnX )
{
    static qboolean s_yawInitialized = false;
    static qboolean snap_debounced = false;

    if (!s_yawInitialized)
    {
        // The player's physical head pose is the initial view. Seeding the
        // turn offset with the first command's view yaw double-counted it on
        // the next frame (spawning while looking sideways rotated the world).
        s_playerTurnYaw = 0.0f;
        s_yawInitialized = true;
    }

    qboolean lefthanded = (vr_lefthanded && vr_lefthanded->value > 0.0f);

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
            float turnSpeed = 150.0f; // degrees per second
            s_playerTurnYaw -= rawTurnX * turnSpeed * frametime;
        }
    }
    s_playerTurnYaw = anglemod( s_playerTurnYaw );

    // Direct 6DoF aim pose mapping to server command viewangles
    vec3_t handOrigin, handAngles;
    if (XR_GetPrimaryHandTransform( handOrigin, handAngles ))
    {
        vec3_t worldAimAngles;
        // Clamp pitch to [-89, 89] to prevent AngleVectors forward vector from flipping sign upside-down
        worldAimAngles[0] = bound( -89.0f, handAngles[0], 89.0f );
        worldAimAngles[1] = anglemod( handAngles[1] + s_playerTurnYaw );
        worldAimAngles[2] = handAngles[2];

        VectorCopy( worldAimAngles, cmd->viewangles );

        // Locomotion decoupling: vr_walkdirection 0: Headset | 1: Controller
        vec3_t headAngles;
        XR_GetHeadOrientation( headAngles );
        float headWorldYaw = anglemod( headAngles[1] + s_playerTurnYaw );

        float walkRefYaw = headWorldYaw;
        if (vr_walkdirection && vr_walkdirection->value == 1.0f)
        {
            // For controller-oriented locomotion, use the offhand / locomotion thumbstick controller orientation
            vec3_t offOrigin, offAngles;
            if (XR_GetSecondaryHandTransform( offOrigin, offAngles ))
                walkRefYaw = anglemod( offAngles[1] + s_playerTurnYaw );
            else
                walkRefYaw = worldAimAngles[1];
        }

        // The engine applies forward/side move along cmd->viewangles (the hand
        // aim), so rotate the stick vector by (hand - walkRef) to express the
        // intended walk direction. Using (walkRef - hand) mirrors the vector
        // when the head turns away from the hand.
        float deltaYaw = worldAimAngles[1] - walkRefYaw;
        float rad = deltaYaw * (3.14159265f / 180.0f);
        float cosA = cosf(rad);
        float sinA = sinf(rad);

        float forwardMove = rawMoveY * cosA - rawMoveX * sinA;
        float sideMove    = rawMoveY * sinA + rawMoveX * cosA;

        if( vr_test_move_probe && vr_test_move_probe->value > 0.0f )
        {
            static double s_nextMoveProbe = 0.0;

            if( host.realtime >= s_nextMoveProbe )
            {
                s_nextMoveProbe = host.realtime + 0.5;
                Con_Printf( "[VR_MOVE] head=%.1f hand=%.1f delta=%.1f fwd=%.1f side=%.1f (simHead=%.0f headYaw=%.0f simHands=%.0f handYaw=%.0f turn=%.1f)\n",
                    walkRefYaw, worldAimAngles[1], deltaYaw, forwardMove, sideMove,
                    vr_test_head ? vr_test_head->value : -1.0f,
                    vr_test_head_yaw ? vr_test_head_yaw->value : -1.0f,
                    vr_test_hands ? vr_test_hands->value : -1.0f,
                    vr_test_hand_yaw ? vr_test_hand_yaw->value : -1.0f,
                    s_playerTurnYaw );
            }
        }

        cmd->forwardmove += forwardMove * 320.0f;
        cmd->sidemove    += sideMove * 320.0f;
    }
    else
    {
        cmd->viewangles[1] = s_playerTurnYaw;
        cmd->forwardmove += rawMoveY * 320.0f;
        cmd->sidemove    += rawMoveX * 320.0f;
    }

    // Clamp forward and side movement to maximum engine thresholds
    cmd->forwardmove = bound(-400.0f, cmd->forwardmove, 400.0f);
    cmd->sidemove    = bound(-400.0f, cmd->sidemove, 400.0f);

    if( vr_test_move_probe && vr_test_move_probe->value > 0.0f )
    {
        static double s_nextFinalProbe = 0.0;

        if( host.realtime >= s_nextFinalProbe )
        {
            s_nextFinalProbe = host.realtime + 0.5;
            Con_Printf( "[VR_MOVE] final cmd fwd=%.1f side=%.1f msec=%d\n",
                cmd->forwardmove, cmd->sidemove, cmd->msec );
        }
    }
}

// Off-hand grip pick-up. The engine only forwards the hand position; the game
// DLL performs the authoritative entity search and Touch() call.
static void XR_ProcessOffhandGrab( qboolean lefthanded )
{
    static qboolean s_prevGrip = false;

    if( !vr_offhand_grab || vr_offhand_grab->value <= 0.0f )
    {
        s_prevGrip = false;
        return;
    }

    float grip = lefthanded ? g_xrInputState.gripRight : g_xrInputState.gripLeft;
    qboolean held = ( grip > 0.55f );

    if( !held )
    {
        s_prevGrip = false;
        return;
    }

    if( s_prevGrip )
        return;

    s_prevGrip = true;

    // Off-hand grip on the weapon is two-handed stabilization, not a grab.
    if( XR_IsTwoHandStabilized( ))
        return;

    vec3_t offOrigin;
    if( !XR_GetSecondaryHandTransform( offOrigin, NULL ))
        return;

    float scale = ( vr_worldscale && vr_worldscale->value > 0.0f ) ? vr_worldscale->value : 40.0f;
    float rad = DEG2RAD( XR_GetPlayerTurnYaw( ));
    float cy = cosf( rad ), sy = sinf( rad );

    vec3_t world;
    world[0] = refState.vieworg[0] + ( offOrigin[0] * cy - offOrigin[1] * sy ) * scale;
    world[1] = refState.vieworg[1] + ( offOrigin[0] * sy + offOrigin[1] * cy ) * scale;
    world[2] = refState.vieworg[2] + offOrigin[2] * scale;

    Cbuf_AddText( va( "vr_grab %.1f %.1f %.1f\n", world[0], world[1], world[2] ));

    if( vr_debug_grab && vr_debug_grab->value > 0.0f )
        Con_Printf( "[VR_GRAB] request at %.1f %.1f %.1f\n", world[0], world[1], world[2] );

    XR_TriggerHapticEffect( lefthanded ? VR_HAND_RIGHT : VR_HAND_LEFT, VR_HAPTIC_UI_CLICK, 0.5f );
}

void XR_InputAppendMove( usercmd_t *cmd, float frametime )
{
    if (!g_xrSessionRunning) return;

    qboolean lefthanded = (vr_lefthanded && vr_lefthanded->value > 0.0f);

    float rawMoveX = lefthanded ? g_xrInputState.turnX : g_xrInputState.moveX;
    float rawMoveY = lefthanded ? g_xrInputState.turnY : g_xrInputState.moveY;
    float rawTurnX = lefthanded ? g_xrInputState.moveX : g_xrInputState.turnX;
    float rawTurnY = lefthanded ? g_xrInputState.moveY : g_xrInputState.turnY;

    // Deterministic stick values for the locomotion regression test.
    if( vr_test_stick_x && vr_test_stick_x->value != 0.0f )
        rawMoveX = vr_test_stick_x->value;
    if( vr_test_stick_y && vr_test_stick_y->value != 0.0f )
        rawMoveY = vr_test_stick_y->value;

    // Live thumbstick 6DOF weapon calibration (Team Beef / Lambda1VR PR #2339)
    XR_ProcessThumbstickCalibration( cmd, lefthanded, &rawTurnX, &rawTurnY );

    // Dominant vs off-hand hands (HL2:VR architecture):
    qboolean attackDominant = lefthanded ? g_xrInputState.attack2 : g_xrInputState.attack;
    qboolean attackOffhand  = lefthanded ? g_xrInputState.attack  : g_xrInputState.attack2;
    float gripDominant      = lefthanded ? g_xrInputState.gripLeft : g_xrInputState.gripRight;

    // Face buttons and stick clicks.
    // Right-handed: Right A = jump, Right B = reload.
    // Left-handed:  Left X  = jump, Left Y  = reload.
    // The action itself never changes; only the physical button source does.
    qboolean btnReload = lefthanded ? g_xrInputState.reloadLeft : g_xrInputState.reload;
    qboolean btnJump   = lefthanded ? g_xrInputState.jumpLeft   : g_xrInputState.jump;

    qboolean stickCrouch = lefthanded ? g_xrInputState.sprint : g_xrInputState.duck;
    qboolean stickSprint = lefthanded ? g_xrInputState.duck   : g_xrInputState.sprint;

    XR_ProcessButtonInputs( cmd, lefthanded, gripDominant, attackDominant,
                            btnReload, btnJump, stickCrouch, stickSprint );
    XR_ProcessHeadFlashlightGesture( cmd, lefthanded );
    XR_ProcessWeaponSelectionGestures( cmd, lefthanded, rawTurnY, attackDominant );
    XR_ProcessTouchToUse( cmd, lefthanded, attackOffhand );
    XR_ProcessOffhandGrab( lefthanded );
    XR_ProcessProximityScope( cmd, lefthanded );
    XR_ProcessPhysicalMeleeSwing( cmd, lefthanded );
    XR_ProcessLocomotionAndTurn( cmd, frametime, rawMoveX, rawMoveY, rawTurnX );
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

qboolean XR_GetSecondaryHandTransform( vec3_t out_origin, vec3_t out_angles )
{
    if (vr_lefthanded && vr_lefthanded->value > 0.0f)
        return XR_GetRightHandTransform( out_origin, out_angles );
    return XR_GetLeftHandTransform( out_origin, out_angles );
}

// Hand presence must follow the raw controller pose. Weapon calibration
// (vr_weapon_*adjust and the per-weapon pitch/yaw/roll profile) rotates the
// viewmodel, and must never leak into the always-visible hands.
static qboolean s_rawHandPose = false;

/*
=============
XR_GetHandPresenceTransform

Returns the 6DoF pose used for persistent hand rendering. Unlike the gameplay
transforms this never fails while the session is active: if a controller has not
been located yet (or was never tracked) a neutral resting pose in front of the
headset is returned, so hand presence never pops out of existence.
=============
*/
qboolean XR_GetHandPresenceTransform( int hand, vec3_t out_origin, vec3_t out_angles )
{
    qboolean valid;
    qboolean prevRaw = s_rawHandPose;

    s_rawHandPose = true;
    if( hand == VR_HAND_RIGHT )
        valid = XR_GetRightHandTransform( out_origin, out_angles );
    else
        valid = XR_GetLeftHandTransform( out_origin, out_angles );
    s_rawHandPose = prevRaw;

    if( valid && out_angles && vr_test_hand_angle_probe && vr_test_hand_angle_probe->value > 0.0f )
    {
        static double s_nextHandAngleProbe = 0.0;

        if( host.realtime >= s_nextHandAngleProbe )
        {
            s_nextHandAngleProbe = host.realtime + 0.5;
            Con_Printf( "[VR_HAND_ANGLES] hand=%s p=%.1f y=%.1f r=%.1f\n",
                ( hand == VR_HAND_RIGHT ) ? "R" : "L",
                out_angles[0], out_angles[1], out_angles[2] );
        }
    }

    if( valid )
        return true;

    if( !XR_IsActive() )
        return false;

    // Neutral resting pose used before the first valid controller sample
    if( out_origin )
    {
        out_origin[0] = 0.22f;   // 22cm forward
        out_origin[1] = ( hand == VR_HAND_LEFT ) ? 0.10f : -0.10f;
        out_origin[2] = -0.10f;  // 10cm below eyes
    }

    if( out_angles )
    {
        out_angles[0] = 0.0f;
        out_angles[1] = 0.0f;
        out_angles[2] = 0.0f;
    }

    return true;
}

void XR_GetFingerCurlAxes( int hand, float *out_trigger, float *out_grip, float *out_thumb )
{
    float trg = 0.0f, grp = 0.0f, thm = 0.0f;

    if (vr_test_finger_curl && vr_test_finger_curl->value > 0.0f)
    {
        trg = (hand == VR_HAND_LEFT) ? 0.75f : 0.85f;
        grp = (hand == VR_HAND_LEFT) ? 0.60f : 0.90f;
        thm = (hand == VR_HAND_LEFT) ? 0.70f : 0.80f;
    }
    else
    {
        if (hand == VR_HAND_LEFT)
        {
            trg = g_xrInputState.triggerLeft;
            grp = g_xrInputState.gripLeft;
            thm = g_xrInputState.thumbLeft;
        }
        else
        {
            trg = g_xrInputState.triggerRight;
            grp = g_xrInputState.gripRight;
            thm = g_xrInputState.thumbRight;
        }
    }

    if (out_trigger) *out_trigger = bound(0.0f, trg, 1.0f);
    if (out_grip)    *out_grip    = bound(0.0f, grp, 1.0f);
    if (out_thumb)   *out_thumb   = bound(0.0f, thm, 1.0f);
}

qboolean XR_GetPrimaryHandMuzzleTransform( vec3_t out_muzzle_offset, vec3_t out_aim_angles )
{
    if (!g_xrSessionRunning) return false;

    vec3_t handOrigin, handAngles;
    if (!XR_GetPrimaryHandTransform( handOrigin, handAngles )) return false;

    float scale = (vr_worldscale && vr_worldscale->value > 0.0f) ? vr_worldscale->value : 40.0f;
    float turn_yaw = XR_GetPlayerTurnYaw();

    vec3_t local_angles;
    local_angles[0] = handAngles[0];
    local_angles[1] = anglemod( handAngles[1] + turn_yaw );
    local_angles[2] = handAngles[2];

    // Query per-weapon calibration profile
    int muzzle_att = 0;
    vec3_t muzzle_fallback = { 0.0f, 14.0f, 0.0f };
    float w_pitch = 0.0f, w_yaw = 0.0f, w_roll = 0.0f;

    const char *wpn = ( clgame.viewent.model && clgame.viewent.model->name[0] ) ? clgame.viewent.model->name : "";

    if( wpn[0] )
    {
        XR_GetWeaponMuzzleParams( wpn, &muzzle_att, muzzle_fallback );
        XR_GetWeaponPitchAdjust( wpn, &w_pitch, &w_yaw, &w_roll );
    }

    local_angles[0] += w_pitch;
    local_angles[1] = anglemod( local_angles[1] + w_yaw );
    local_angles[2] += w_roll;

    if( out_aim_angles )
    {
        VectorCopy( local_angles, out_aim_angles );
    }

    if( out_muzzle_offset )
    {
        // 1. If viewmodel already has attachment computed by studio bone transformation, use it directly
        if( muzzle_att >= 0 && muzzle_att < 4 && clgame.viewent.model && !VectorIsNull( clgame.viewent.attachment[muzzle_att] ) &&
            VectorDistance( clgame.viewent.attachment[muzzle_att], refState.vieworg ) < 80.0f )
        {
            VectorSubtract( clgame.viewent.attachment[muzzle_att], refState.vieworg, out_muzzle_offset );
        }
        else
        {
            // 2. Base weapon pose (single source of truth), then add the
            //    synthetic barrel extension in the same weapon frame.
            vec3_t pose_origin, pose_angles;
            XR_GetWeaponPose( wpn, handOrigin, handAngles, turn_yaw, refState.vieworg, scale,
                pose_origin, pose_angles );

            vec3_t forward, right, up;
            AngleVectors( pose_angles, forward, right, up );

            // Include barrel extension so ballistics match viewmodel and laser sight
            float barrel_len = (muzzle_fallback[1] > 0.0f) ? muzzle_fallback[1] : 18.0f;
            float barrel_up  = muzzle_fallback[2];
            float off_fwd = barrel_len;
            float off_rt  = muzzle_fallback[0];
            float off_up  = barrel_up;

            // pose_origin is world; convert back to the vieworg-relative offset
            // this function is contracted to return.
            out_muzzle_offset[0] = (pose_origin[0] - refState.vieworg[0]) + forward[0] * off_fwd + right[0] * off_rt + up[0] * off_up;
            out_muzzle_offset[1] = (pose_origin[1] - refState.vieworg[1]) + forward[1] * off_fwd + right[1] * off_rt + up[1] * off_up;
            out_muzzle_offset[2] = (pose_origin[2] - refState.vieworg[2]) + forward[2] * off_fwd + right[2] * off_rt + up[2] * off_up;
        }

        Con_DPrintf( "[VR_GRIP] src=muzzle model=%s origin=(%.2f %.2f %.2f) world=(%.2f %.2f %.2f) angles=(%.2f %.2f %.2f) lefthanded=%d pullback=0\n",
            wpn, out_muzzle_offset[0], out_muzzle_offset[1], out_muzzle_offset[2],
            out_muzzle_offset[0] + refState.vieworg[0], out_muzzle_offset[1] + refState.vieworg[1], out_muzzle_offset[2] + refState.vieworg[2],
            local_angles[0], local_angles[1], local_angles[2],
            (vr_lefthanded && vr_lefthanded->value > 0.0f) ? 1 : 0 );
    }

    return true;
}

qboolean XR_GetPrimaryHandMuzzleWorldPosition( vec3_t out_world_muzzle )
{
    if (!g_xrSessionRunning) return false;

    int muzzle_att = 0;
    vec3_t muzzle_fallback = { 0.0f, 18.0f, 0.0f };
    if( clgame.viewent.model && clgame.viewent.model->name[0] )
    {
        XR_GetWeaponMuzzleParams( clgame.viewent.model->name, &muzzle_att, muzzle_fallback );
    }

    // 1. If viewmodel has a projected muzzle attachment point from studio bone transformation, prefer it
    if( muzzle_att >= 0 && muzzle_att < 4 && clgame.viewent.model && !VectorIsNull( clgame.viewent.attachment[muzzle_att] ) )
    {
        if( VectorDistance( clgame.viewent.attachment[muzzle_att], refState.vieworg ) < 80.0f )
        {
            VectorCopy( clgame.viewent.attachment[muzzle_att], out_world_muzzle );
            return true;
        }
    }

    // 2. Direct canonical fallback calculation from 6DoF hand pose and weapon muzzle calibration
    vec3_t muzzleOffset, aimAngles;
    if( XR_GetPrimaryHandMuzzleTransform( muzzleOffset, aimAngles ) )
    {
        VectorAdd( refState.vieworg, muzzleOffset, out_world_muzzle );
        return true;
    }

    return false;
}


static qboolean s_twoHandEngaged = false;

qboolean XR_IsTwoHandStabilized( void )
{
    return s_twoHandEngaged;
}

static void XR_ApplyTwoHandStabilizer( const XrPosef *primaryPose, const XrPosef *offPose, float offGrip, qboolean offActive, vec3_t out_angles )
{
    qboolean twohanded_enabled = (vr_twohanded && vr_twohanded->value > 0.0f);
    qboolean weapon_allows_twohand = true;
    float min_hand_dist = 0.12f;
    float max_hand_dist = 0.65f;

    if( clgame.viewent.model && clgame.viewent.model->name[0] )
    {
        XR_GetWeaponTwoHandParams( clgame.viewent.model->name, &weapon_allows_twohand, &min_hand_dist, &max_hand_dist );
    }

    if (!twohanded_enabled || !offActive || !weapon_allows_twohand)
    {
        s_twoHandEngaged = false;
        XR_QuatToEuler( &primaryPose->orientation, out_angles );
        return;
    }

    // Relative vector from primary hand to offhand in OpenXR tracking space
    float ox = offPose->position.x - primaryPose->position.x;
    float oy = offPose->position.y - primaryPose->position.y;
    float oz = offPose->position.z - primaryPose->position.z;
    float handDist = sqrtf(ox * ox + oy * oy + oz * oz);

    // Convert vector into GoldSrc coordinates: Forward = -oz, Left = -ox, Up = oy
    vec3_t aimDir;
    aimDir[0] = -oz;
    aimDir[1] = -ox;
    aimDir[2] =  oy;

    // Geometric spatial gating (derived from FEAR VR & Lambda1VR ergonomics and per-weapon manifest):
    // 1. Off-hand must be in front of the primary hand (aimDir[0] >= 0.05m and <= max_hand_dist + 0.05m)
    // 2. Off-hand cannot be excessively separated laterally (|aimDir[1]| <= 0.28m)
    // 3. Hand separation floor calibrated per weapon
    qboolean inSpatialVolume = (aimDir[0] >= 0.05f && aimDir[0] <= (max_hand_dist + 0.05f) &&
                                fabsf(aimDir[1]) <= 0.28f &&
                                handDist >= min_hand_dist && handDist <= max_hand_dist);

    // Grip hysteresis to prevent micro-flickering
    if (!s_twoHandEngaged)
    {
        if (offGrip > 0.55f && inSpatialVolume)
        {
            s_twoHandEngaged = true;
        }
    }
    else
    {
        if (offGrip < 0.35f || !inSpatialVolume)
        {
            s_twoHandEngaged = false;
        }
    }

    if (s_twoHandEngaged)
    {
        vec3_t baseAngles, twoHandAngles;
        XR_QuatToEuler( &primaryPose->orientation, baseAngles );

        VectorNormalize( aimDir );
        VectorAngles( aimDir, twoHandAngles );

        // Preserve primary hand's natural weapon roll
        twoHandAngles[2] = baseAngles[2];

        // Soft Asymptotic Clamp: avoid sudden stop when aiming at steep angles relative to wrist
        float yawDiff = anglemod(twoHandAngles[1] - baseAngles[1]);
        if (yawDiff > 180.0f) yawDiff -= 360.0f;
        float pitchDiff = twoHandAngles[0] - baseAngles[0];
        float dev = sqrtf(yawDiff * yawDiff + pitchDiff * pitchDiff);

        if (dev > 50.0f)
        {
            float softDev = 50.0f + (dev - 50.0f) * 0.40f;
            if (softDev > 85.0f) softDev = 85.0f;
            float factor = softDev / dev;
            twoHandAngles[0] = baseAngles[0] + pitchDiff * factor;
            twoHandAngles[1] = anglemod(baseAngles[1] + yawDiff * factor);
        }

        VectorCopy( twoHandAngles, out_angles );
    }
    else
    {
        XR_QuatToEuler( &primaryPose->orientation, out_angles );
    }
}

qboolean XR_GetRightHandTransform( vec3_t out_origin, vec3_t out_angles )
{
    if (!g_xrSessionRunning) return false;

    // Simulated hand pose override for testing and validation
    if (vr_test_hands && vr_test_hands->value > 0.0f)
    {
        if (out_origin)
        {
            out_origin[0] = 0.22f;   // 22cm forward
            out_origin[1] = -0.06f;  // 6cm right (GoldSrc coordinates)
            out_origin[2] = -0.08f;  // 8cm below eyes
        }

        if (out_angles)
        {
            out_angles[0] = vr_test_hand_pitch ? vr_test_hand_pitch->value : 0.0f;
            out_angles[1] = vr_test_hand_yaw ? vr_test_hand_yaw->value : 0.0f;
            out_angles[2] = 0.0f;

            if (!s_rawHandPose)
            {
                if (vr_weapon_pitchadjust && vr_weapon_pitchadjust->value != 0.0f)
                    out_angles[0] += vr_weapon_pitchadjust->value;
                if (vr_weapon_yawadjust && vr_weapon_yawadjust->value != 0.0f)
                    out_angles[1] = anglemod(out_angles[1] + vr_weapon_yawadjust->value);
                if (vr_weapon_rolladjust && vr_weapon_rolladjust->value != 0.0f)
                    out_angles[2] += vr_weapon_rolladjust->value;
            }
        }

        return true;
    }

    if (!g_xrInputState.rightHandActive)
        return false;

    // Convert to head-relative GoldSrc coordinates:
    // X = forward (-rel_z), Y = left (-rel_x), Z = up (rel_y)
    if (out_origin)
    {
        float rel_x = g_xrInputState.rightHandPose.position.x - g_xrViews[0].pose.position.x;
        float rel_y = g_xrInputState.rightHandPose.position.y - g_xrViews[0].pose.position.y;
        float rel_z = g_xrInputState.rightHandPose.position.z - g_xrViews[0].pose.position.z;

        out_origin[0] = -rel_z;
        out_origin[1] = -rel_x;
        out_origin[2] =  rel_y;
    }

    if (out_angles)
    {
        qboolean lefthanded = (vr_lefthanded && vr_lefthanded->value > 0.0f);
        if (!s_rawHandPose && !lefthanded)
        {
            // Right hand is primary weapon hand; stabilized by left hand grip
            XR_ApplyTwoHandStabilizer( &g_xrInputState.rightHandPose, &g_xrInputState.leftHandPose,
                                      g_xrInputState.gripLeft, g_xrInputState.leftHandActive, out_angles );
        }
        else
        {
            XR_QuatToEuler( &g_xrInputState.rightHandPose.orientation, out_angles );
        }

        if (!s_rawHandPose)
        {
            float w_pitch = 0.0f, w_yaw = 0.0f, w_roll = 0.0f;
            if( !lefthanded && clgame.viewent.model && clgame.viewent.model->name[0] )
            {
                XR_GetWeaponPitchAdjust( clgame.viewent.model->name, &w_pitch, &w_yaw, &w_roll );
            }

            if( (vr_weapon_pitchadjust && vr_weapon_pitchadjust->value != 0.0f) || w_pitch != 0.0f )
            {
                out_angles[0] += (vr_weapon_pitchadjust ? vr_weapon_pitchadjust->value : 0.0f) + w_pitch;
            }
            if( (vr_weapon_yawadjust && vr_weapon_yawadjust->value != 0.0f) || w_yaw != 0.0f )
            {
                out_angles[1] = anglemod(out_angles[1] + (vr_weapon_yawadjust ? vr_weapon_yawadjust->value : 0.0f) + w_yaw);
            }
            if( (vr_weapon_rolladjust && vr_weapon_rolladjust->value != 0.0f) || w_roll != 0.0f )
            {
                out_angles[2] += (vr_weapon_rolladjust ? vr_weapon_rolladjust->value : 0.0f) + w_roll;
            }
        }
    }

    return true;
}

qboolean XR_GetLeftHandTransform( vec3_t out_origin, vec3_t out_angles )
{
    if (!g_xrSessionRunning) return false;

    // Simulated hand pose override for testing and validation
    if (vr_test_hands && vr_test_hands->value > 0.0f)
    {
        if (out_origin)
        {
            out_origin[0] = 0.22f;
            out_origin[1] = 0.06f;   // 6cm to the left
            out_origin[2] = -0.08f;
        }

        if (out_angles)
        {
            out_angles[0] = vr_test_hand_pitch ? vr_test_hand_pitch->value : 0.0f;
            out_angles[1] = vr_test_hand_yaw ? vr_test_hand_yaw->value : 0.0f;
            out_angles[2] = 0.0f;

            if (!s_rawHandPose)
            {
                if (vr_weapon_pitchadjust && vr_weapon_pitchadjust->value != 0.0f)
                    out_angles[0] += vr_weapon_pitchadjust->value;
                if (vr_weapon_yawadjust && vr_weapon_yawadjust->value != 0.0f)
                    out_angles[1] = anglemod(out_angles[1] + vr_weapon_yawadjust->value);
                if (vr_weapon_rolladjust && vr_weapon_rolladjust->value != 0.0f)
                    out_angles[2] += vr_weapon_rolladjust->value;
            }
        }

        return true;
    }

    if (!g_xrInputState.leftHandActive)
        return false;

    // Convert to head-relative GoldSrc coordinates:
    if (out_origin)
    {
        float rel_x = g_xrInputState.leftHandPose.position.x - g_xrViews[0].pose.position.x;
        float rel_y = g_xrInputState.leftHandPose.position.y - g_xrViews[0].pose.position.y;
        float rel_z = g_xrInputState.leftHandPose.position.z - g_xrViews[0].pose.position.z;

        out_origin[0] = -rel_z;
        out_origin[1] = -rel_x;
        out_origin[2] =  rel_y;
    }

    if (out_angles)
    {
        qboolean lefthanded = (vr_lefthanded && vr_lefthanded->value > 0.0f);
        if (!s_rawHandPose && lefthanded)
        {
            // Left hand is primary weapon hand; stabilized by right hand grip
            XR_ApplyTwoHandStabilizer( &g_xrInputState.leftHandPose, &g_xrInputState.rightHandPose,
                                      g_xrInputState.gripRight, g_xrInputState.rightHandActive, out_angles );
        }
        else
        {
            XR_QuatToEuler( &g_xrInputState.leftHandPose.orientation, out_angles );
        }

        if (!s_rawHandPose)
        {
            float w_pitch = 0.0f, w_yaw = 0.0f, w_roll = 0.0f;
            if( lefthanded && clgame.viewent.model && clgame.viewent.model->name[0] )
            {
                XR_GetWeaponPitchAdjust( clgame.viewent.model->name, &w_pitch, &w_yaw, &w_roll );
            }

            if( (vr_weapon_pitchadjust && vr_weapon_pitchadjust->value != 0.0f) || w_pitch != 0.0f )
            {
                out_angles[0] += (vr_weapon_pitchadjust ? vr_weapon_pitchadjust->value : 0.0f) + w_pitch;
            }
            if( (vr_weapon_yawadjust && vr_weapon_yawadjust->value != 0.0f) || w_yaw != 0.0f )
            {
                out_angles[1] = anglemod(out_angles[1] + (vr_weapon_yawadjust ? vr_weapon_yawadjust->value : 0.0f) + w_yaw);
            }
            if( (vr_weapon_rolladjust && vr_weapon_rolladjust->value != 0.0f) || w_roll != 0.0f )
            {
                out_angles[2] += (vr_weapon_rolladjust ? vr_weapon_rolladjust->value : 0.0f) + w_roll;
            }
        }
    }

    return true;
}

qboolean XR_GetRightHandVelocity( vec3_t out_velocity )
{
    if (!g_xrSessionRunning || !g_xrInputState.rightHandActive) return false;

    // Linear velocity conversion to GoldSrc room coordinates:
    // OpenXR room space: -Z is forward, +X is right, +Y is up
    // GoldSrc room space: +X is forward (-Z), +Y is left (-X), +Z is up (+Y)
    float roomX = -g_xrInputState.rightHandVelocity.z;
    float roomY = -g_xrInputState.rightHandVelocity.x;
    float roomZ = g_xrInputState.rightHandVelocity.y;

    // Rotate horizontal velocity by player turn yaw
    float rad = s_playerTurnYaw * (3.14159265f / 180.0f);
    float cosYaw = cosf(rad);
    float sinYaw = sinf(rad);

    out_velocity[0] = roomX * cosYaw - roomY * sinYaw;
    out_velocity[1] = roomX * sinYaw + roomY * cosYaw;
    out_velocity[2] = roomZ;
    return true;
}

qboolean XR_GetLeftHandVelocity( vec3_t out_velocity )
{
    if (!g_xrSessionRunning || !g_xrInputState.leftHandActive) return false;

    float roomX = -g_xrInputState.leftHandVelocity.z;
    float roomY = -g_xrInputState.leftHandVelocity.x;
    float roomZ = g_xrInputState.leftHandVelocity.y;

    float rad = s_playerTurnYaw * (3.14159265f / 180.0f);
    float cosYaw = cosf(rad);
    float sinYaw = sinf(rad);

    out_velocity[0] = roomX * cosYaw - roomY * sinYaw;
    out_velocity[1] = roomX * sinYaw + roomY * cosYaw;
    out_velocity[2] = roomZ;
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

	float fire_amp = 0.0f, fire_dur = 0.0f;
	if( clgame.viewent.model && clgame.viewent.model->name[0] &&
	    XR_GetWeaponHaptics( clgame.viewent.model->name, &fire_amp, &fire_dur ) && fire_amp > 0.0f )
	{
		float dur_sec = bound( 0.02f, fire_dur * 0.001f, 0.5f );
		XR_ApplyHapticFeedback( primary_hand, dur_sec, 200.0f, fire_amp );
		return;
	}

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

typedef struct {
	qboolean active;
	qboolean hit;
	float u, v;
	int x, y;
	int startX, startY;
	vec3_t rayStart;
	vec3_t rayEnd;
} vr_pointer_hand_state_t;

static vr_pointer_hand_state_t s_pointerHands[2] = {0};
static int s_activePointerHand = VR_HAND_RIGHT;
static qboolean s_prevHandTrigger[2] = {false, false};
// Toggle menu visibility when menu button is pressed
static void XR_ProcessMenuToggle( void )
{
	static qboolean s_prevMenuButton = false;
	static double s_nextMenuToggleTime = 0.0;
	qboolean menuPressed = g_xrInputState.menu;

	if( menuPressed && !s_prevMenuButton && host.realtime >= s_nextMenuToggleTime )
	{
		s_nextMenuToggleTime = host.realtime + 0.35;
		Con_Printf( "[VR_MENU] toggle requested (UI_IsVisible=%d key_dest=%d state=%d)\n",
			UI_IsVisible(), (int)cls.key_dest, (int)cls.state );
		XR_TriggerHapticEffect( s_activePointerHand, VR_HAPTIC_UI_CLICK, 0.5f );

		if( UI_IsVisible() || cls.key_dest == key_menu || cls.key_dest == key_console )
		{
			// In-menu: cleanly close menu and return to gameplay
			Key_Event( K_ESCAPE, true );
			Key_Event( K_ESCAPE, false );
			UI_SetActiveMenu( false );
			cls.key_dest = key_game;

			// Closing the mainui menu does not clear the server pause flag.
			// Toggle it back so the game resumes after the menu button.
			if( cl.paused )
				Cbuf_AddText( "pause\n" );
		}
		else
		{
			// In-game: open the in-headset menu
			UI_SetActiveMenu( true );
		}
	}
	s_prevMenuButton = menuPressed;
}

// Compute laser pointer ray cast and quad intersection for a specific hand
static void XR_TracePointerRayForHand( int hand, XrTime syncTime, XrSpace targetQuadSpace,
                                       qboolean useMenuSpace, float menuDist, float worldScale,
                                       float quadWidth, float quadHeight, float halfW, float halfH )
{
	XrSpace handSpace = (hand == VR_HAND_LEFT) ? g_leftHandSpace : g_rightHandSpace;
	XrPosef poseInTarget = {0};
	qboolean hasPose = false;
	float dx = 0.0f, dy = 0.0f, dz = -1.0f;

	// 1. Simulated hand pose override (for automated test environments)
	if( vr_test_hands && vr_test_hands->value > 0.0f )
	{
		poseInTarget.position.x = (hand == VR_HAND_LEFT) ? -0.15f : 0.15f;
		poseInTarget.position.y = -0.15f;
		poseInTarget.position.z = useMenuSpace ? 1.20f : -0.30f;

		float pitch = vr_test_hand_pitch ? vr_test_hand_pitch->value : 0.0f;
		float yaw   = vr_test_hand_yaw ? vr_test_hand_yaw->value : 0.0f;
		float pitch_rad = DEG2RAD( pitch );
		float yaw_rad   = DEG2RAD( yaw );

		// View space / quad space: +X Right, +Y Up, -Z Forward towards quad
		dx =  sinf( yaw_rad ) * cosf( pitch_rad );
		dy = -sinf( pitch_rad );
		dz = -cosf( yaw_rad ) * cosf( pitch_rad );

		hasPose = true;
	}
	// 2. Locate physical controller in target Quad Space or View Space
	else if( handSpace != XR_NULL_HANDLE )
	{
		XrSpace refSpace = useMenuSpace ? targetQuadSpace : g_xrViewSpace;
		if( refSpace != XR_NULL_HANDLE && syncTime > 0 )
		{
			XrSpaceLocation loc = {0};
			loc.type = XR_TYPE_SPACE_LOCATION;
			if( XR_SUCCEEDED( xrLocateSpace( handSpace, refSpace, syncTime, &loc ) ))
			{
				if( loc.locationFlags & XR_SPACE_LOCATION_POSITION_VALID_BIT )
				{
					poseInTarget = loc.pose;
					hasPose = true;

					float qx = poseInTarget.orientation.x;
					float qy = poseInTarget.orientation.y;
					float qz = poseInTarget.orientation.z;
					float qw = poseInTarget.orientation.w;

					dx = -2.0f * (qx * qz + qw * qy);
					dy = -2.0f * (qy * qz - qw * qx);
					dz = -1.0f + 2.0f * (qx * qx + qy * qy);
				}
			}
		}
	}

	if( !hasPose )
	{
		s_pointerHands[hand].active = false;
		s_pointerHands[hand].hit = false;
		return;
	}

	float len = sqrtf( dx * dx + dy * dy + dz * dz );
	if( len > 0.0001f )
	{
		dx /= len;
		dy /= len;
		dz /= len;
	}

	qboolean hit = false;
	float u = 0.5f, v = 0.5f;
	int px = 0, py = 0;

	// Plane target: In menu space, quad sits at Z=0. In fallback view space, quad sits at Z=-menuDist.
	float planeZ = useMenuSpace ? 0.0f : -menuDist;

	vec3_t rayStart, rayEnd;
	rayStart[0] = -poseInTarget.position.z * worldScale;
	rayStart[1] = -poseInTarget.position.x * worldScale;
	rayStart[2] =  poseInTarget.position.y * worldScale;

	float hit_x = poseInTarget.position.x + 2.0f * dx;
	float hit_y = poseInTarget.position.y + 2.0f * dy;
	float hit_z = poseInTarget.position.z + 2.0f * dz;

	if( dz < -0.01f )
	{
		float t = (planeZ - poseInTarget.position.z) / dz;
		if( t > 0.0f )
		{
			float ix = poseInTarget.position.x + t * dx;
			float iy = poseInTarget.position.y + t * dy;

			if( ix >= -halfW && ix <= halfW && iy >= -halfH && iy <= halfH )
			{
				u = (ix + halfW) / quadWidth;
				v = (halfH - iy) / quadHeight; // top of screen (v=0) is +halfH
				u = bound( 0.0f, u, 1.0f );
				v = bound( 0.0f, v, 1.0f );

				if( refState.width > 0 && refState.height > 0 )
				{
					px = bound( 0, (int)(u * (float)refState.width), refState.width - 1 );
					py = bound( 0, (int)(v * (float)refState.height), refState.height - 1 );
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

	s_pointerHands[hand].active = true;
	s_pointerHands[hand].hit = hit;
	s_pointerHands[hand].u = u;
	s_pointerHands[hand].v = v;
	s_pointerHands[hand].x = px;
	s_pointerHands[hand].y = py;

	// Project the controller position onto the menu plane so the 2D menu
	// cursor can draw a laser from the hand to the hit point. The eye sits at
	// z=0 in view space (quad at -menuDist) or z=menuDist in menu space (quad
	// at 0).
	{
		float eyeZ = useMenuSpace ? menuDist : 0.0f;
		float denom = poseInTarget.position.z - eyeZ;
		float sx = (float)px, sy = (float)py;

		if( refState.width > 0 && refState.height > 0 )
		{
			if( fabsf( denom ) > 0.001f )
			{
				float t = (planeZ - eyeZ) / denom;
				if( t > 0.0f && t < 20.0f )
				{
					float ix = poseInTarget.position.x * t;
					float iy = poseInTarget.position.y * t;
					float su = (ix + halfW) / quadWidth;
					float sv = (halfH - iy) / quadHeight;

					sx = su * (float)refState.width;
					sy = sv * (float)refState.height;
				}
			}

			sx = bound( 0.0f, sx, (float)refState.width - 1.0f );
			sy = bound( 0.0f, sy, (float)refState.height - 1.0f );
		}

		s_pointerHands[hand].startX = (int)sx;
		s_pointerHands[hand].startY = (int)sy;
	}

	VectorCopy( rayStart, s_pointerHands[hand].rayStart );
	VectorCopy( rayEnd, s_pointerHands[hand].rayEnd );
}

// Process pointer trigger events and active hand switching
static void XR_ProcessPointerTriggers( void )
{
	qboolean triggerLeft = g_xrInputState.attack2;
	qboolean triggerRight = g_xrInputState.attack;

	if( vr_test_click && vr_test_click->value > 0.0f )
	{
		if( (int)vr_test_click->value == 2 )
			triggerLeft = true;
		else
			triggerRight = true;
	}

	// Left Hand Trigger Edge Detection
	if( triggerLeft && !s_prevHandTrigger[VR_HAND_LEFT] )
	{
		s_activePointerHand = VR_HAND_LEFT;
		if( s_pointerHands[VR_HAND_LEFT].hit && refState.width > 0 && refState.height > 0 )
		{
			UI_MouseMove( s_pointerHands[VR_HAND_LEFT].x, s_pointerHands[VR_HAND_LEFT].y );
			VGui_MouseMove( s_pointerHands[VR_HAND_LEFT].x, s_pointerHands[VR_HAND_LEFT].y );
		}
		XR_TriggerHapticEffect( VR_HAND_LEFT, VR_HAPTIC_UI_CLICK, 0.6f );
		Con_Printf( "^2[VR_POINTER] Switched active pointer to LEFT hand (click at screen: %d, %d)\n",
			s_pointerHands[VR_HAND_LEFT].x, s_pointerHands[VR_HAND_LEFT].y );
		Key_Event( K_MOUSE1, true );
	}
	else if( !triggerLeft && s_prevHandTrigger[VR_HAND_LEFT] )
	{
		if( s_activePointerHand == VR_HAND_LEFT )
			Key_Event( K_MOUSE1, false );
	}
	s_prevHandTrigger[VR_HAND_LEFT] = triggerLeft;

	// Right Hand Trigger Edge Detection
	if( triggerRight && !s_prevHandTrigger[VR_HAND_RIGHT] )
	{
		s_activePointerHand = VR_HAND_RIGHT;
		if( s_pointerHands[VR_HAND_RIGHT].hit && refState.width > 0 && refState.height > 0 )
		{
			UI_MouseMove( s_pointerHands[VR_HAND_RIGHT].x, s_pointerHands[VR_HAND_RIGHT].y );
			VGui_MouseMove( s_pointerHands[VR_HAND_RIGHT].x, s_pointerHands[VR_HAND_RIGHT].y );
		}
		XR_TriggerHapticEffect( VR_HAND_RIGHT, VR_HAPTIC_UI_CLICK, 0.6f );
		Con_Printf( "^2[VR_POINTER] Switched active pointer to RIGHT hand (click at screen: %d, %d)\n",
			s_pointerHands[VR_HAND_RIGHT].x, s_pointerHands[VR_HAND_RIGHT].y );
		Key_Event( K_MOUSE1, true );
	}
	else if( !triggerRight && s_prevHandTrigger[VR_HAND_RIGHT] )
	{
		if( s_activePointerHand == VR_HAND_RIGHT )
			Key_Event( K_MOUSE1, false );
	}
	s_prevHandTrigger[VR_HAND_RIGHT] = triggerRight;
}

// Process analog thumbstick wheel scroll
static void XR_ProcessPointerScroll( void )
{
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

void XR_UpdatePointerCursor( void )
{
	if( !g_xrSessionRunning || !XR_IsActive() )
	{
		s_pointerHands[0].active = false;
		s_pointerHands[0].hit = false;
		s_pointerHands[1].active = false;
		s_pointerHands[1].hit = false;
		return;
	}

	XR_ProcessMenuToggle();

	static qboolean s_wasInMenu = false;
	qboolean in_menu = (UI_IsVisible() || cls.key_dest == key_menu || cls.key_dest == key_console || cls.state == ca_disconnected);
	if( !in_menu )
	{
		s_wasInMenu = false;
		XR_SetQuadHud( false );
		s_pointerHands[0].active = false;
		s_pointerHands[0].hit = false;
		s_pointerHands[1].active = false;
		s_pointerHands[1].hit = false;
		return;
	}

	if( in_menu && !s_wasInMenu )
	{
		XR_ResetMenuAnchor();
		s_wasInMenu = true;
	}

	XR_SetQuadHud( true );

	if( vr_pointer_hud && vr_pointer_hud->value == 0.0f )
	{
		s_pointerHands[0].active = false;
		s_pointerHands[1].active = false;
		return;
	}

	float menuDist = (vr_menu_distance && vr_menu_distance->value > 0.5f) ? vr_menu_distance->value : 1.15f;
	float worldScale = (vr_worldscale && vr_worldscale->value > 0.0f) ? vr_worldscale->value : 40.0f;

	// Ergonomic floating menu dimensions: 1.15m width fits comfortably within central central FOV
	float quadWidth = (vr_menu_scale && vr_menu_scale->value > 0.5f) ? vr_menu_scale->value : 1.15f;
	float aspect = (refState.width > 0 && refState.height > 0) ? ((float)refState.height / (float)refState.width) : 0.75f;
	float quadHeight = quadWidth * aspect;
	float halfW = quadWidth * 0.5f;
	float halfH = quadHeight * 0.5f;

	XrTime syncTime = XR_GetPredictedDisplayTime();
	XrSpace targetQuadSpace = XR_GetMenuQuadSpace();
	qboolean useMenuSpace = (targetQuadSpace != XR_NULL_HANDLE);

	// Process both left and right hands for dual-pointer support (Beat Saber style)
	for( int hand = 0; hand < 2; hand++ )
	{
		XR_TracePointerRayForHand( hand, syncTime, targetQuadSpace, useMenuSpace, menuDist, worldScale,
		                           quadWidth, quadHeight, halfW, halfH );
	}

	XR_ProcessPointerTriggers();

	// Continuous hover updates driven by the active pointer hand
	if( s_pointerHands[s_activePointerHand].active && s_pointerHands[s_activePointerHand].hit )
	{
		if( refState.width > 0 && refState.height > 0 )
		{
			UI_MouseMove( s_pointerHands[s_activePointerHand].x, s_pointerHands[s_activePointerHand].y );
			VGui_MouseMove( s_pointerHands[s_activePointerHand].x, s_pointerHands[s_activePointerHand].y );
		}
	}

	static int s_ptrDbgTimer = 0;
	if( ++s_ptrDbgTimer >= 30 )
	{
		s_ptrDbgTimer = 0;
		if( vr_test_hands && vr_test_hands->value > 0.0f )
		{
			Con_Printf( "^3[VR_POINTER] activeHand=%s L_hit=%d R_hit=%d screen=(%d, %d) uv=(%.2f, %.2f)\n",
				(s_activePointerHand == VR_HAND_LEFT) ? "LEFT" : "RIGHT",
				s_pointerHands[VR_HAND_LEFT].hit,
				s_pointerHands[VR_HAND_RIGHT].hit,
				s_pointerHands[s_activePointerHand].x,
				s_pointerHands[s_activePointerHand].y,
				s_pointerHands[s_activePointerHand].u,
				s_pointerHands[s_activePointerHand].v );
		}
	}

	XR_ProcessPointerScroll();
}

qboolean XR_GetPointerLaserRayHand( int hand, vec3_t out_start, vec3_t out_end, qboolean *out_hit, float *out_u, float *out_v )
{
	if( hand < 0 || hand > 1 )
		return false;
	if( !s_pointerHands[hand].active )
		return false;

	if( out_start ) VectorCopy( s_pointerHands[hand].rayStart, out_start );
	if( out_end ) VectorCopy( s_pointerHands[hand].rayEnd, out_end );
	if( out_hit ) *out_hit = s_pointerHands[hand].hit;
	if( out_u ) *out_u = s_pointerHands[hand].u;
	if( out_v ) *out_v = s_pointerHands[hand].v;
	return true;
}

qboolean XR_GetPointerLaserRay( vec3_t out_start, vec3_t out_end, qboolean *out_hit, float *out_u, float *out_v )
{
	return XR_GetPointerLaserRayHand( s_activePointerHand, out_start, out_end, out_hit, out_u, out_v );
}

qboolean XR_GetPointerLaserScreen( int hand, int *out_sx, int *out_sy, int *out_ex, int *out_ey, qboolean *out_hit )
{
	if( hand < 0 || hand > 1 )
		return false;
	if( !s_pointerHands[hand].active )
		return false;

	if( out_sx ) *out_sx = s_pointerHands[hand].startX;
	if( out_sy ) *out_sy = s_pointerHands[hand].startY;
	if( out_ex ) *out_ex = s_pointerHands[hand].x;
	if( out_ey ) *out_ey = s_pointerHands[hand].y;
	if( out_hit ) *out_hit = s_pointerHands[hand].hit;
	return true;
}

int XR_GetActivePointerHand( void )
{
	return s_activePointerHand;
}

qboolean XR_GetPointerCursorPos( int *out_x, int *out_y, qboolean *out_hit )
{
	if( !s_pointerHands[s_activePointerHand].active )
		return false;

	if( out_x ) *out_x = s_pointerHands[s_activePointerHand].x;
	if( out_y ) *out_y = s_pointerHands[s_activePointerHand].y;
	if( out_hit ) *out_hit = s_pointerHands[s_activePointerHand].hit;
	return true;
}

#endif // XASH_OPENXR
