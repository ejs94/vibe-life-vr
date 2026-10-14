#include "common.h"
#include "xr_core.h"
#include "client/vid_common.h"
#include <SDL.h>

#ifdef XASH_OPENXR

#if !defined(__ANDROID__)
#define XR_USE_PLATFORM_XLIB
#define XR_USE_GRAPHICS_API_OPENGL
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <GL/glx.h>
#include <openxr/openxr.h>
#include <openxr/openxr_platform.h>
#include <SDL_syswm.h>
#else
#define XR_USE_PLATFORM_ANDROID
#define XR_USE_GRAPHICS_API_OPENGL_ES
#include <jni.h>
#include <EGL/egl.h>
#include <openxr/openxr.h>
#include <openxr/openxr_platform.h>
#endif

#if !defined(__ANDROID__)
static PFN_xrGetOpenGLGraphicsRequirementsKHR pfnGetOpenGLGraphicsRequirementsKHR = NULL;
static XrGraphicsBindingOpenGLXlibKHR g_graphicsBindingGLX;
#else
static PFN_xrGetOpenGLESGraphicsRequirementsKHR pfnGetOpenGLESGraphicsRequirementsKHR = NULL;
static XrGraphicsBindingOpenGLESAndroidKHR g_graphicsBindingGLES;
static EGLSurface g_savedSurface = EGL_NO_SURFACE;
#endif

qboolean XR_InitGraphics( void )
{
    if (g_xrInstance == XR_NULL_HANDLE || g_xrSystemId == XR_NULL_SYSTEM_ID)
    {
        Con_Printf("XR_InitGraphics: Invalid OpenXR instance or system ID!\n");
        return false;
    }

#if !defined(__ANDROID__)
    XrResult res = xrGetInstanceProcAddr(
        g_xrInstance,
        "xrGetOpenGLGraphicsRequirementsKHR",
        (PFN_xrVoidFunction*)&pfnGetOpenGLGraphicsRequirementsKHR
    );

    if (XR_FAILED(res) || !pfnGetOpenGLGraphicsRequirementsKHR)
    {
        Con_Printf("XR_InitGraphics: Failed to get xrGetOpenGLGraphicsRequirementsKHR (res = %d)\n", res);
        return false;
    }

    XrGraphicsRequirementsOpenGLKHR glReqs = {0};
    glReqs.type = XR_TYPE_GRAPHICS_REQUIREMENTS_OPENGL_KHR;

    res = pfnGetOpenGLGraphicsRequirementsKHR(g_xrInstance, g_xrSystemId, &glReqs);
    if (XR_FAILED(res))
    {
        Con_Printf("XR_InitGraphics: xrGetOpenGLGraphicsRequirementsKHR failed (res = %d)\n", res);
        return false;
    }

    if (!host.hWnd)
    {
        Con_Printf("XR_InitGraphics: host.hWnd not yet created!\n");
        return false;
    }

    SDL_SysWMinfo wmInfo;
    SDL_VERSION(&wmInfo.version);
    if (!SDL_GetWindowWMInfo((SDL_Window*)host.hWnd, &wmInfo))
    {
        Con_Printf("XR_InitGraphics: SDL_GetWindowWMInfo failed: %s\n", SDL_GetError());
        return false;
    }

    Display *xDisplay = wmInfo.info.x11.display;
    GLXContext glxContext = (GLXContext)glw_state.context;
    GLXDrawable glxDrawable = (GLXDrawable)wmInfo.info.x11.window;

    GLXContext curCtx = glXGetCurrentContext();
    GLXDrawable curDraw = glXGetCurrentDrawable();
    Display *curDpy = glXGetCurrentDisplay();

    Con_Printf("XR_InitGraphics: wmInfo dpy=%p win=%lx; current dpy=%p ctx=%p draw=%lx (glw ctx=%p)\n",
        (void*)xDisplay, (unsigned long)glxDrawable, (void*)curDpy, (void*)curCtx, (unsigned long)curDraw, (void*)glxContext);

    if (curCtx) glxContext = curCtx;
    if (curDraw) glxDrawable = curDraw;
    if (curDpy) xDisplay = curDpy;

    memset(&g_graphicsBindingGLX, 0, sizeof(g_graphicsBindingGLX));
    g_graphicsBindingGLX.type = XR_TYPE_GRAPHICS_BINDING_OPENGL_XLIB_KHR;
    g_graphicsBindingGLX.xDisplay = xDisplay;
    g_graphicsBindingGLX.glxContext = glxContext;
    g_graphicsBindingGLX.glxDrawable = glxDrawable;

    // Issue #6: OpenXR Xlib binding strictly requires valid glxFBConfig and visualid
    int fbconfig_id = 0;
    int screen = DefaultScreen(xDisplay);
    glXQueryContext(xDisplay, glxContext, GLX_SCREEN, &screen);
    if (glXQueryContext(xDisplay, glxContext, GLX_FBCONFIG_ID, &fbconfig_id) == 0 && fbconfig_id > 0)
    {
        int attribs[] = {
            GLX_FBCONFIG_ID, fbconfig_id,
            None
        };
        int nconfigs = 0;
        GLXFBConfig *configs = glXChooseFBConfig(xDisplay, screen, attribs, &nconfigs);
        if (configs && nconfigs > 0)
        {
            g_graphicsBindingGLX.glxFBConfig = configs[0];
            int vid = 0;
            glXGetFBConfigAttrib(xDisplay, configs[0], GLX_VISUAL_ID, &vid);
            g_graphicsBindingGLX.visualid = (uint32_t)vid;
            XFree(configs);
        }
    }

    if (!g_graphicsBindingGLX.glxFBConfig)
    {
        int fb_attribs[] = {
            GLX_RENDER_TYPE, GLX_RGBA_BIT,
            GLX_DRAWABLE_TYPE, GLX_WINDOW_BIT,
            GLX_DOUBLEBUFFER, True,
            GLX_RED_SIZE, 8,
            GLX_GREEN_SIZE, 8,
            GLX_BLUE_SIZE, 8,
            None
        };
        int nconfigs = 0;
        GLXFBConfig *configs = glXChooseFBConfig(xDisplay, screen, fb_attribs, &nconfigs);
        if (configs && nconfigs > 0)
        {
            g_graphicsBindingGLX.glxFBConfig = configs[0];
            int vid = 0;
            glXGetFBConfigAttrib(xDisplay, configs[0], GLX_VISUAL_ID, &vid);
            g_graphicsBindingGLX.visualid = (uint32_t)vid;
            XFree(configs);
        }
    }

    if (g_graphicsBindingGLX.visualid == 0)
    {
        XWindowAttributes winAttr;
        if (XGetWindowAttributes(xDisplay, (Window)glxDrawable, &winAttr) && winAttr.visual)
        {
            g_graphicsBindingGLX.visualid = (uint32_t)XVisualIDFromVisual(winAttr.visual);
        }
    }

    Con_Printf("XR_InitGraphics: OpenGL Xlib PCVR Graphics Binding initialized (fbConfig=%p, visualid=0x%x)\n",
        (void*)g_graphicsBindingGLX.glxFBConfig, g_graphicsBindingGLX.visualid);
    return true;
#else
    XrResult res = xrGetInstanceProcAddr(
        g_xrInstance,
        "xrGetOpenGLESGraphicsRequirementsKHR",
        (PFN_xrVoidFunction*)&pfnGetOpenGLESGraphicsRequirementsKHR
    );

    if (XR_FAILED(res) || !pfnGetOpenGLESGraphicsRequirementsKHR)
    {
        Con_Printf("XR_InitGraphics: Failed to get xrGetOpenGLESGraphicsRequirementsKHR (res = %d)\n", res);
        return false;
    }

    XrGraphicsRequirementsOpenGLESKHR glesReqs = {0};
    glesReqs.type = XR_TYPE_GRAPHICS_REQUIREMENTS_OPENGL_ES_KHR;

    res = pfnGetOpenGLESGraphicsRequirementsKHR(g_xrInstance, g_xrSystemId, &glesReqs);
    if (XR_FAILED(res))
    {
        Con_Printf("XR_InitGraphics: xrGetOpenGLESGraphicsRequirementsKHR failed (res = %d)\n", res);
        return false;
    }

    Con_Printf("XR_InitGraphics: GLES requirements: min=%u.%u.%u, max=%u.%u.%u\n",
        XR_VERSION_MAJOR(glesReqs.minApiVersionSupported),
        XR_VERSION_MINOR(glesReqs.minApiVersionSupported),
        XR_VERSION_PATCH(glesReqs.minApiVersionSupported),
        XR_VERSION_MAJOR(glesReqs.maxApiVersionSupported),
        XR_VERSION_MINOR(glesReqs.maxApiVersionSupported),
        XR_VERSION_PATCH(glesReqs.maxApiVersionSupported));

    memset(&g_graphicsBindingGLES, 0, sizeof(g_graphicsBindingGLES));
    g_graphicsBindingGLES.type = XR_TYPE_GRAPHICS_BINDING_OPENGL_ES_ANDROID_KHR;
    g_graphicsBindingGLES.display = eglGetCurrentDisplay();
    g_graphicsBindingGLES.context = eglGetCurrentContext();
    g_savedSurface = eglGetCurrentSurface(EGL_DRAW);

    EGLint configId = 0;
    EGLConfig config = NULL;
    if (eglQueryContext(g_graphicsBindingGLES.display, g_graphicsBindingGLES.context, EGL_CONFIG_ID, &configId))
    {
        EGLint attribs[] = { EGL_CONFIG_ID, configId, EGL_NONE };
        EGLint numConfigs = 0;
        if (eglChooseConfig(g_graphicsBindingGLES.display, attribs, &config, 1, &numConfigs) && numConfigs > 0)
        {
            Con_Printf("XR_InitGraphics: Found EGLConfig (ID %d)\n", configId);
        }
        else
        {
            Con_Printf("XR_InitGraphics: Failed to get EGLConfig for ID %d\n", configId);
        }
    }
    else
    {
        Con_Printf("XR_InitGraphics: Failed to query EGL_CONFIG_ID from context (err 0x%x)\n", eglGetError());
    }
    g_graphicsBindingGLES.config = config;

    Con_Printf("XR_InitGraphics: OpenGL ES Meta Quest Standalone Graphics Binding initialized successfully (display=%p, ctx=%p, sfc=%p, cfg=%p)!\n",
               g_graphicsBindingGLES.display, g_graphicsBindingGLES.context, g_savedSurface, g_graphicsBindingGLES.config);
    return true;
#endif
}

void XR_EnsureCurrent( void )
{
#if defined(__ANDROID__)
    EGLContext cur = eglGetCurrentContext();
    Con_Printf("XR_EnsureCurrent: curCtx = %p (bindingCtx = %p)\n", cur, g_graphicsBindingGLES.context);
    if (cur == EGL_NO_CONTEXT)
    {
        Con_Printf("XR_EnsureCurrent: Context was not current! (cur=%p, savedCtx=%p, savedDpy=%p, savedSfc=%p)\n",
                   cur, g_graphicsBindingGLES.context, g_graphicsBindingGLES.display, g_savedSurface);
        if (g_graphicsBindingGLES.display != EGL_NO_DISPLAY && g_graphicsBindingGLES.context != EGL_NO_CONTEXT)
        {
            EGLBoolean ok = eglMakeCurrent(g_graphicsBindingGLES.display, g_savedSurface, g_savedSurface, g_graphicsBindingGLES.context);
            Con_Printf("XR_EnsureCurrent: eglMakeCurrent returned %d (err 0x%x), cur=%p\n",
                       ok, eglGetError(), eglGetCurrentContext());
        }
        if (eglGetCurrentContext() == EGL_NO_CONTEXT && host.hWnd && glw_state.context)
        {
            Con_Printf("XR_EnsureCurrent: Trying SDL_GL_MakeCurrent...\n");
            SDL_GL_MakeCurrent((SDL_Window*)host.hWnd, glw_state.context);
            Con_Printf("XR_EnsureCurrent: After SDL_GL_MakeCurrent, cur=%p\n", eglGetCurrentContext());
        }
    }
#endif
}

void* XR_GetGraphicsBinding( void )
{
#if !defined(__ANDROID__)
    return &g_graphicsBindingGLX;
#else
    return &g_graphicsBindingGLES;
#endif
}

#endif // XASH_OPENXR
