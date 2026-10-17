#include "common.h"
#include "xr_core.h"
#include "xr_swapchain.h"
#include "xr_input.h"
#include <openxr/openxr.h>
#include <stdlib.h>
#include <string.h>

#ifdef __ANDROID__
#include <jni.h>
#include <SDL_system.h>
#ifndef XR_USE_PLATFORM_ANDROID
#define XR_USE_PLATFORM_ANDROID
#endif
#include <openxr/openxr_platform.h>
#endif

#ifdef XASH_OPENXR

XrInstance g_xrInstance = XR_NULL_HANDLE;
XrSystemId g_xrSystemId = XR_NULL_SYSTEM_ID;
XrSession g_xrSession = XR_NULL_HANDLE;
XrSpace g_xrLocalSpace = XR_NULL_HANDLE;
XrSpace g_xrViewSpace = XR_NULL_HANDLE;
XrSessionState g_xrSessionState = XR_SESSION_STATE_UNKNOWN;
qboolean g_xrSessionRunning = false;

EXPORT convar_t *vr_smoothturn = NULL;
EXPORT convar_t *vr_snap_angle = NULL;
EXPORT convar_t *vr_walkdirection = NULL;
EXPORT convar_t *vr_lasersight = NULL;
EXPORT convar_t *vr_headtorch = NULL;
EXPORT convar_t *vr_lefthanded = NULL;
EXPORT convar_t *vr_weapon_pitchadjust = NULL;
EXPORT convar_t *vr_weapon_yawadjust = NULL;
EXPORT convar_t *vr_weapon_rolladjust = NULL;
EXPORT convar_t *vr_weapon_offset_forward = NULL;
EXPORT convar_t *vr_weapon_offset_right = NULL;
EXPORT convar_t *vr_weapon_offset_up = NULL;
EXPORT convar_t *vr_height_adjust = NULL;
EXPORT convar_t *vr_hide_arms = NULL;
EXPORT convar_t *vr_twohanded = NULL;
EXPORT convar_t *vr_menu_distance = NULL;
EXPORT convar_t *vr_menu_scale = NULL;
EXPORT convar_t *vr_worldscale = NULL;
EXPORT convar_t *vr_haptics_enabled = NULL;
EXPORT convar_t *vr_haptics_intensity = NULL;
EXPORT convar_t *vr_pointer_hud = NULL;
EXPORT convar_t *vr_test_hands = NULL;
EXPORT convar_t *vr_test_hand_pitch = NULL;
EXPORT convar_t *vr_test_hand_yaw = NULL;
EXPORT convar_t *vr_test_click = NULL;
EXPORT convar_t *vr_test_head = NULL;
EXPORT convar_t *vr_test_head_pitch = NULL;
EXPORT convar_t *vr_test_head_yaw = NULL;
EXPORT convar_t *vr_test_head_roll = NULL;
EXPORT convar_t *vr_test_headgesture = NULL;
EXPORT convar_t *vr_audio_hrtf = NULL;
EXPORT convar_t *vr_finger_curling = NULL;
EXPORT convar_t *vr_finger_curl_scale = NULL;
EXPORT convar_t *vr_offhand_render = NULL;
EXPORT convar_t *vr_test_finger_curl = NULL;
static XrDebugUtilsMessengerEXT g_xrDebugMessenger = XR_NULL_HANDLE;

static qboolean s_cvarsRegistered = false;

void XR_RegisterCVars( void )
{
    if (s_cvarsRegistered) return;
    s_cvarsRegistered = true;

    vr_smoothturn = Cvar_Get("vr_smoothturn", "1", FCVAR_ARCHIVE, "Smooth turn (1) or snap turn (0)");
    vr_snap_angle = Cvar_Get("vr_snap_angle", "45", FCVAR_ARCHIVE, "Snap turn angle");
    vr_walkdirection = Cvar_Get("vr_walkdirection", "0", FCVAR_ARCHIVE, "0 = HMD direction, 1 = Controller orientation");
    vr_lasersight = Cvar_Get("vr_lasersight", "1", FCVAR_ARCHIVE, "Enable 3D weapon laser sight");
    vr_headtorch = Cvar_Get("vr_headtorch", "1", FCVAR_ARCHIVE, "Head-mounted flashlight following view direction (HL2:VR style)");
    vr_lefthanded = Cvar_Get("vr_lefthanded", "0", FCVAR_ARCHIVE, "1 = Left-handed primary weapon");
    vr_weapon_pitchadjust = Cvar_Get("vr_weapon_pitchadjust", "0", FCVAR_ARCHIVE, "Weapon barrel pitch adjust degrees");
    vr_weapon_yawadjust = Cvar_Get("vr_weapon_yawadjust", "0", FCVAR_ARCHIVE, "Weapon barrel yaw adjust degrees");
    vr_weapon_rolladjust = Cvar_Get("vr_weapon_rolladjust", "0", FCVAR_ARCHIVE, "Weapon barrel roll adjust degrees");
    vr_weapon_offset_forward = Cvar_Get("vr_weapon_offset_forward", "0", FCVAR_ARCHIVE, "Weapon grip forward offset (GoldSrc units)");
    vr_weapon_offset_right = Cvar_Get("vr_weapon_offset_right", "0", FCVAR_ARCHIVE, "Weapon grip right offset (GoldSrc units)");
    vr_weapon_offset_up = Cvar_Get("vr_weapon_offset_up", "0", FCVAR_ARCHIVE, "Weapon grip up offset (GoldSrc units)");
    vr_height_adjust = Cvar_Get("vr_height_adjust", "0", FCVAR_ARCHIVE, "Player height adjust units");
    vr_hide_arms = Cvar_Get("vr_hide_arms", "1", FCVAR_ARCHIVE, "Hide flat-screen HEV arm/glove meshes on viewmodel in VR");
    vr_twohanded = Cvar_Get("vr_twohanded", "0", FCVAR_ARCHIVE, "Enable two-handed weapon grip stabilization");
    vr_menu_distance = Cvar_Get("vr_menu_distance", "2.1", FCVAR_ARCHIVE, "Distance in meters of floating 2D menu quad");
    vr_menu_scale = Cvar_Get("vr_menu_scale", "1.8", FCVAR_ARCHIVE, "Width in meters of floating 2D menu quad");
    vr_worldscale = Cvar_Get("vr_worldscale", "40.0", FCVAR_ARCHIVE, "VR World Scale (units per meter)");
    vr_haptics_enabled = Cvar_Get("vr_haptics_enabled", "1", FCVAR_ARCHIVE, "Enable OpenXR haptic vibration feedback");
    vr_haptics_intensity = Cvar_Get("vr_haptics_intensity", "1.0", FCVAR_ARCHIVE, "VR haptic vibration feedback intensity multiplier");
    vr_pointer_hud = Cvar_Get("vr_pointer_hud", "1", FCVAR_ARCHIVE, "Enable VR laser pointer cursor in menus");
    vr_audio_hrtf = Cvar_Get("vr_audio_hrtf", "1", FCVAR_ARCHIVE, "Enable 3D binaural HRTF spatial audio & pinna shadowing in VR");
    vr_finger_curling = Cvar_Get("vr_finger_curling", "1", FCVAR_ARCHIVE, "Enable procedural finger curling driven by controller analog axes");
    vr_finger_curl_scale = Cvar_Get("vr_finger_curl_scale", "1.0", FCVAR_ARCHIVE, "Multiplier for procedural finger curling angle");
    vr_offhand_render = Cvar_Get("vr_offhand_render", "1", FCVAR_ARCHIVE, "Enable 6DoF secondary off-hand rendering and hand presence");
    vr_test_finger_curl = Cvar_Get("vr_test_finger_curl", "0", 0, "Simulate finger curling axes for headless regression testing");
    vr_test_hands = Cvar_Get("vr_test_hands", "0", 0, "Simulate 6DoF hand pose when physical controllers unavailable");
    vr_test_hand_pitch = Cvar_Get("vr_test_hand_pitch", "0", 0, "Simulated hand aim pitch degrees");
    vr_test_hand_yaw = Cvar_Get("vr_test_hand_yaw", "0", 0, "Simulated hand aim yaw degrees");
    vr_test_click = Cvar_Get("vr_test_click", "0", 0, "Simulate controller trigger click for UI/weapon testing");
    vr_test_head = Cvar_Get("vr_test_head", "0", 0, "Simulate head orientation for testing (0 = off, 1 = on)");
    vr_test_head_pitch = Cvar_Get("vr_test_head_pitch", "0", 0, "Simulated head pitch degrees");
    vr_test_head_yaw = Cvar_Get("vr_test_head_yaw", "0", 0, "Simulated head yaw degrees");
    vr_test_head_roll = Cvar_Get("vr_test_head_roll", "0", 0, "Simulated head roll degrees");
    vr_test_headgesture = Cvar_Get("vr_test_headgesture", "0", 0, "Simulate head flashlight gesture (1 = right hand, 2 = left hand)");
}

#define OXR_CHECK(func, msg) \
    do { \
        XrResult res = (func); \
        if (XR_FAILED(res)) { \
            Con_Printf("OpenXR Error: %s failed with code %d\n", msg, res); \
            return false; \
        } \
    } while(0)

static XRAPI_ATTR XrBool32 XRAPI_CALL XR_DebugUtilsCallback(
    XrDebugUtilsMessageSeverityFlagsEXT severity,
    XrDebugUtilsMessageTypeFlagsEXT type,
    const XrDebugUtilsMessengerCallbackDataEXT *callbackData,
    void *userData)
{
    (void)type;
    (void)userData;
    const char *sevPrefix = "DEBUG";
    if (severity & XR_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT) {
        sevPrefix = "ERROR";
    } else if (severity & XR_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT) {
        sevPrefix = "WARN";
    } else if (severity & XR_DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT) {
        sevPrefix = "INFO";
    }

    Con_Printf("[OpenXR %s] [%s] %s\n",
        sevPrefix,
        callbackData && callbackData->functionName ? callbackData->functionName : "unknown",
        callbackData && callbackData->message ? callbackData->message : "");

    return XR_FALSE;
}

qboolean XR_Init( void )
{
    XR_RegisterCVars();

    Con_Printf("XR_Init: Initializing Khronos OpenXR Runtime...\n");

#ifdef __ANDROID__
    PFN_xrInitializeLoaderKHR pfnXrInitializeLoaderKHR = NULL;
    xrGetInstanceProcAddr(XR_NULL_HANDLE, "xrInitializeLoaderKHR", (PFN_xrVoidFunction*)&pfnXrInitializeLoaderKHR);

    JavaVM *vm = NULL;
    void *activity = NULL;

    JNIEnv *env = (JNIEnv*)SDL_AndroidGetJNIEnv();
    if (env)
    {
        (*env)->GetJavaVM(env, &vm);
    }
    activity = SDL_AndroidGetActivity();

    if (pfnXrInitializeLoaderKHR)
    {
        if (vm && activity)
        {
            XrLoaderInitInfoAndroidKHR initInfoAndroid;
            memset(&initInfoAndroid, 0, sizeof(initInfoAndroid));
            initInfoAndroid.type = XR_TYPE_LOADER_INIT_INFO_ANDROID_KHR;
            initInfoAndroid.applicationVM = vm;
            initInfoAndroid.applicationContext = activity;

            XrResult lRes = pfnXrInitializeLoaderKHR((const XrLoaderInitInfoBaseHeaderKHR*)&initInfoAndroid);
            if (XR_FAILED(lRes))
            {
                Con_Printf("XR_Init: xrInitializeLoaderKHR failed with code %d\n", lRes);
                return false;
            }
            Con_Printf("XR_Init: xrInitializeLoaderKHR initialized successfully!\n");
        }
        else
        {
            Con_Printf("XR_Init: Failed to retrieve JavaVM (%p) or Activity (%p) from SDL!\n", vm, activity);
            return false;
        }
    }
    else
    {
        Con_Printf("XR_Init: xrInitializeLoaderKHR not exported or not needed by loader.\n");
    }
#endif

    // Query supported instance extensions
    uint32_t extCount = 0;
    xrEnumerateInstanceExtensionProperties(NULL, 0, &extCount, NULL);
    XrExtensionProperties *extProps = NULL;
    if (extCount > 0)
    {
        extProps = (XrExtensionProperties*)malloc(extCount * sizeof(XrExtensionProperties));
        if (extProps)
        {
            for (uint32_t i = 0; i < extCount; i++)
            {
                extProps[i].type = XR_TYPE_EXTENSION_PROPERTIES;
                extProps[i].next = NULL;
            }
            xrEnumerateInstanceExtensionProperties(NULL, extCount, &extCount, extProps);
        }
    }

    const char* enabledExtensions[16];
    uint32_t enabledExtCount = 0;

#if !defined(__ANDROID__)
    const char *desiredExts[] = {
        "XR_KHR_opengl_enable",
        "XR_EXT_debug_utils"
    };
#else
    const char *desiredExts[] = {
        "XR_KHR_opengl_es_enable",
        "XR_KHR_android_create_instance",
        "XR_EXT_debug_utils"
    };
#endif

    for (size_t d = 0; d < sizeof(desiredExts)/sizeof(desiredExts[0]); d++)
    {
        qboolean found = false;
        if (extProps)
        {
            for (uint32_t i = 0; i < extCount; i++)
            {
                if (!strcmp(extProps[i].extensionName, desiredExts[d]))
                {
                    found = true;
                    break;
                }
            }
        }
        else
        {
            found = true;
        }

        if (found && enabledExtCount < 16)
        {
            enabledExtensions[enabledExtCount++] = desiredExts[d];
            Con_Printf("XR_Init: Requesting extension: %s\n", desiredExts[d]);
        }
        else
        {
            Con_Printf("XR_Init: Extension not supported by runtime: %s\n", desiredExts[d]);
        }
    }

    if (extProps)
    {
        free(extProps);
    }

    XrInstanceCreateInfo createInfo = {0};
    createInfo.type = XR_TYPE_INSTANCE_CREATE_INFO;
    strcpy(createInfo.applicationInfo.applicationName, "Xash3D VR");
    createInfo.applicationInfo.applicationVersion = 1;
    strcpy(createInfo.applicationInfo.engineName, "Xash3D FWGS");
    createInfo.applicationInfo.engineVersion = 1;
    createInfo.applicationInfo.apiVersion = XR_CURRENT_API_VERSION;

    createInfo.enabledExtensionCount = enabledExtCount;
    createInfo.enabledExtensionNames = enabledExtensions;

#ifdef __ANDROID__
    XrInstanceCreateInfoAndroidKHR instanceCreateInfoAndroid;
    memset(&instanceCreateInfoAndroid, 0, sizeof(instanceCreateInfoAndroid));
    instanceCreateInfoAndroid.type = XR_TYPE_INSTANCE_CREATE_INFO_ANDROID_KHR;
    instanceCreateInfoAndroid.applicationVM = vm;
    instanceCreateInfoAndroid.applicationActivity = activity;

    for (uint32_t i = 0; i < enabledExtCount; i++)
    {
        if (!strcmp(enabledExtensions[i], "XR_KHR_android_create_instance"))
        {
            createInfo.next = &instanceCreateInfoAndroid;
            break;
        }
    }
#endif

    OXR_CHECK(xrCreateInstance(&createInfo, &g_xrInstance), "xrCreateInstance");
    Con_Printf("OpenXR: Khronos instance created successfully!\n");

    // Initialize XR_EXT_debug_utils messenger if available
    PFN_xrCreateDebugUtilsMessengerEXT pfnCreateDebugUtilsMessenger = NULL;
    xrGetInstanceProcAddr(g_xrInstance, "xrCreateDebugUtilsMessengerEXT", (PFN_xrVoidFunction*)&pfnCreateDebugUtilsMessenger);
    if (pfnCreateDebugUtilsMessenger)
    {
        XrDebugUtilsMessengerCreateInfoEXT dbgInfo = {0};
        dbgInfo.type = XR_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT;
        dbgInfo.messageSeverities =
            XR_DEBUG_UTILS_MESSAGE_SEVERITY_VERBOSE_BIT_EXT |
            XR_DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT |
            XR_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT |
            XR_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT;
        dbgInfo.messageTypes =
            XR_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT |
            XR_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT |
            XR_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT |
            XR_DEBUG_UTILS_MESSAGE_TYPE_CONFORMANCE_BIT_EXT;
        dbgInfo.userCallback = XR_DebugUtilsCallback;

        XrResult dbgRes = pfnCreateDebugUtilsMessenger(g_xrInstance, &dbgInfo, &g_xrDebugMessenger);
        if (dbgRes == XR_SUCCESS)
        {
            Con_Printf("OpenXR: XR_EXT_debug_utils messenger attached successfully!\n");
        }
        else
        {
            Con_Printf("OpenXR: Failed to attach XR_EXT_debug_utils messenger: %d\n", dbgRes);
        }
    }

    XrSystemGetInfo systemInfo = {0};
    systemInfo.type = XR_TYPE_SYSTEM_GET_INFO;
    systemInfo.formFactor = XR_FORM_FACTOR_HEAD_MOUNTED_DISPLAY;

    OXR_CHECK(xrGetSystem(g_xrInstance, &systemInfo, &g_xrSystemId), "xrGetSystem");
    Con_Printf("OpenXR: Headset detected, SystemId = %llu\n", (unsigned long long)g_xrSystemId);

    return true;
}

qboolean XR_CreateSession( void )
{
    if (g_xrInstance == XR_NULL_HANDLE || g_xrSystemId == XR_NULL_SYSTEM_ID)
    {
        return false;
    }

    if (!XR_InitGraphics())
    {
        Con_Printf("XR_CreateSession: Failed to initialize graphics for OpenXR!\n");
        return false;
    }

    void *graphicsBinding = XR_GetGraphicsBinding();
    if (!graphicsBinding)
    {
        Con_Printf("XR_CreateSession: Graphics Binding is invalid!\n");
        return false;
    }

    XrSessionCreateInfo sessionCreateInfo = {0};
    sessionCreateInfo.type = XR_TYPE_SESSION_CREATE_INFO;
    sessionCreateInfo.next = graphicsBinding;
    sessionCreateInfo.systemId = g_xrSystemId;

    OXR_CHECK(xrCreateSession(g_xrInstance, &sessionCreateInfo, &g_xrSession), "xrCreateSession");
    Con_Printf("OpenXR: XrSession created successfully!\n");

    // Enumerate supported reference spaces to detect STAGE (Roomscale/Guardian bounds)
    // Inspired by Team Beef (Lambda1VR): prefer STAGE reference space when available to align
    // player tracking with physical floor and Guardian bounds, while providing graceful LOCAL fallback.
    uint32_t spaceCount = 0;
    qboolean stageSupported = false;
    if (XR_SUCCEEDED(xrEnumerateReferenceSpaces(g_xrSession, 0, &spaceCount, NULL)) && spaceCount > 0)
    {
        XrReferenceSpaceType *spaces = (XrReferenceSpaceType*)malloc(sizeof(XrReferenceSpaceType) * spaceCount);
        if (spaces)
        {
            if (XR_SUCCEEDED(xrEnumerateReferenceSpaces(g_xrSession, spaceCount, &spaceCount, spaces)))
            {
                for (uint32_t i = 0; i < spaceCount; i++)
                {
                    if (spaces[i] == XR_REFERENCE_SPACE_TYPE_STAGE)
                    {
                        stageSupported = true;
                        break;
                    }
                }
            }
            free(spaces);
        }
    }

    XrReferenceSpaceCreateInfo spaceInfo = {0};
    spaceInfo.type = XR_TYPE_REFERENCE_SPACE_CREATE_INFO;
    spaceInfo.poseInReferenceSpace.orientation.w = 1.0f;

    if (stageSupported)
    {
        spaceInfo.referenceSpaceType = XR_REFERENCE_SPACE_TYPE_STAGE;
        XrResult res = xrCreateReferenceSpace(g_xrSession, &spaceInfo, &g_xrLocalSpace);
        if (XR_SUCCEEDED(res))
        {
            Con_Printf("OpenXR: Stage Reference Space (Roomscale/Guardian) created successfully!\n");
        }
        else
        {
            Con_Printf("OpenXR: Failed to create Stage space (res=%d), falling back to Local space.\n", res);
            stageSupported = false;
        }
    }

    if (!stageSupported)
    {
        spaceInfo.referenceSpaceType = XR_REFERENCE_SPACE_TYPE_LOCAL;
        OXR_CHECK(xrCreateReferenceSpace(g_xrSession, &spaceInfo, &g_xrLocalSpace), "xrCreateReferenceSpace");
        Con_Printf("OpenXR: Local Reference Space created successfully!\n");
    }

    // Issue #2: Create VIEW reference space (Headset-relative space).
    // An identity pose in VIEW space represents looking directly forward from the headset display/eyes.
    // Quad layers placed in this space (e.g. z = -1.5m) comfortably float directly in front of the player's
    // field of view, regardless of room floor calibration (STAGE) or sitting position.
    XrReferenceSpaceCreateInfo viewSpaceInfo = {0};
    viewSpaceInfo.type = XR_TYPE_REFERENCE_SPACE_CREATE_INFO;
    viewSpaceInfo.referenceSpaceType = XR_REFERENCE_SPACE_TYPE_VIEW;
    viewSpaceInfo.poseInReferenceSpace.orientation.w = 1.0f;
    if (XR_SUCCEEDED(xrCreateReferenceSpace(g_xrSession, &viewSpaceInfo, &g_xrViewSpace)))
    {
        Con_Printf("OpenXR: View Reference Space (Head-relative) created successfully!\n");
    }
    else
    {
        Con_Printf("OpenXR: Failed to create View space, will fallback to Local/Stage space.\n");
    }

    XR_InitInput();

    // Create swapchains right away while graphics context is guaranteed active and current
    XR_CreateSwapchains();

    return true;
}

qboolean XR_IsActive( void )
{
    return g_xrSessionRunning && g_xrSwapchainsReady;
}

void XR_Shutdown( void )
{
    XR_ShutdownInput();
    XR_DestroySwapchains();

    if (g_xrLocalSpace != XR_NULL_HANDLE) {
        xrDestroySpace(g_xrLocalSpace);
        g_xrLocalSpace = XR_NULL_HANDLE;
    }
    if (g_xrViewSpace != XR_NULL_HANDLE) {
        xrDestroySpace(g_xrViewSpace);
        g_xrViewSpace = XR_NULL_HANDLE;
    }
    if (g_xrSession != XR_NULL_HANDLE) {
        if (g_xrSessionRunning) {
            xrEndSession(g_xrSession);
            g_xrSessionRunning = false;
        }
        xrDestroySession(g_xrSession);
        g_xrSession = XR_NULL_HANDLE;
    }
    if (g_xrDebugMessenger != XR_NULL_HANDLE) {
        PFN_xrDestroyDebugUtilsMessengerEXT pfnDestroyDebugUtilsMessenger = NULL;
        xrGetInstanceProcAddr(g_xrInstance, "xrDestroyDebugUtilsMessengerEXT", (PFN_xrVoidFunction*)&pfnDestroyDebugUtilsMessenger);
        if (pfnDestroyDebugUtilsMessenger) {
            pfnDestroyDebugUtilsMessenger(g_xrDebugMessenger);
        }
        g_xrDebugMessenger = XR_NULL_HANDLE;
    }
    if (g_xrInstance != XR_NULL_HANDLE) {
        xrDestroyInstance(g_xrInstance);
        g_xrInstance = XR_NULL_HANDLE;
    }
    g_xrSessionState = XR_SESSION_STATE_UNKNOWN;
}

void XR_PollEvents( void )
{
    if (g_xrInstance == XR_NULL_HANDLE) return;
    
    XrEventDataBuffer event = {0};
    event.type = XR_TYPE_EVENT_DATA_BUFFER;
    
    while (xrPollEvent(g_xrInstance, &event) == XR_SUCCESS) {
        if (event.type == XR_TYPE_EVENT_DATA_SESSION_STATE_CHANGED) {
            XrEventDataSessionStateChanged* stateEvent = (XrEventDataSessionStateChanged*)&event;
            g_xrSessionState = stateEvent->state;
            Con_Printf("OpenXR: Session state changed to: %d\n", g_xrSessionState);

            if (g_xrSessionState == XR_SESSION_STATE_READY) {
                XrSessionBeginInfo beginInfo = {0};
                beginInfo.type = XR_TYPE_SESSION_BEGIN_INFO;
                beginInfo.primaryViewConfigurationType = XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
                
                if (xrBeginSession(g_xrSession, &beginInfo) == XR_SUCCESS) {
                    g_xrSessionRunning = true;
                    Con_Printf("OpenXR: xrBeginSession started successfully! Streaming to headset.\n");
                    if (!g_xrSwapchainsReady)
                    {
                        XR_CreateSwapchains();
                    }
                }
            } else if (g_xrSessionState == XR_SESSION_STATE_STOPPING) {
                if (g_xrSessionRunning) {
                    xrEndSession(g_xrSession);
                    g_xrSessionRunning = false;
                    Con_Printf("OpenXR: xrEndSession completed.\n");
                }
            } else if (g_xrSessionState == XR_SESSION_STATE_LOSS_PENDING || g_xrSessionState == XR_SESSION_STATE_EXITING) {
                XR_Shutdown();
            }
        }
        event.type = XR_TYPE_EVENT_DATA_BUFFER;
    }
}

#endif // XASH_OPENXR
