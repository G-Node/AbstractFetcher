//
//  AFAppDelegate.m
//  AbstractFetcher
//
// Copyright (c) 2012 Christian Kellner <kellner@bio.lmu.de>.
// Permission is hereby granted, free of charge, to any person obtaining
// a copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so, subject to
// the following conditions:
//
// The above copyright notice and this permission notice shall be
// included in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
// EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
// LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
// OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
// WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//

#import "AFAppDelegate.h"
#import "AFArticleRef.h"
#import <WebKit/WebFrameLoadDelegate.h>

typedef enum {
    STATE_IDLE = 0,
    STATE_GET_URLS = 1,
    STATE_GET_ABS = 2,
    STATE_HAVE_URLS = 3,
    STATE_DONE = 4
} AppState;

//#define ABSTRACT_ACCEPTED_URL @"http://www.frontiersin.org/journal/AbstractMyEditingAssignment.aspx?stage=8"
#define ABSTRACT_ACCEPTED_URL @"http://www.frontiersin.org/MyFrontiers/Events/ViewEventAbstractDetail.aspx?va=1&eid=2231&sname=Neuroinformatics_2014"
#define ABSTRACT_DETAIL_URL @"http://www.frontiersin.org/Journal/MyEditingViewDetails.aspx?stage=8"
//#define JS_NEXT_PAGE @"__doPostBack('ctl00$ctl00$MainContentPlaceHolder$ContentAreaMainContent$UcEventsAbstractListing$ucCommunityPagerTop$lnkNextPage','')"

#define JS_NEXT_PAGE @"__doPostBack('ctl00$ctl00$MainContentPlaceHolder$ContentAreaMainContent$UcEventAbstractsListing$ucCommunityPagerTop$lnkNextPage','')"

@interface ReqID : NSObject
@property BOOL isTarget;
@end

@implementation ReqID
@synthesize isTarget = _isTarget;
@end

@interface AFAppDelegate () {
    AppState state;
}

@property (weak) IBOutlet WebView *webview;
@property (weak) IBOutlet NSButton *goButton;
@property (weak) IBOutlet NSTextFieldCell *status;
@property (weak) IBOutlet NSTextFieldCell *statusIndex;
@property (weak) IBOutlet NSProgressIndicator *progress;
@property (weak) IBOutlet NSTextField *location;
@property (weak) IBOutlet NSProgressIndicator *loadIndicator;
@property (weak) IBOutlet NSButton *gatherURLsButton;

@property (nonatomic, strong) NSString *saveLocation;
//@property (nonatomic, strong) NSMutableArray *urls;
@property (nonatomic, strong) NSMutableArray *articleRefs;
@property (nonatomic, strong) NSFileHandle *fdOutput;
@property (nonatomic, readonly) NSURL *currentURL;
@property (nonatomic) NSUInteger idx;

@end


@implementation AFAppDelegate
@synthesize location = _url;
@synthesize loadIndicator = _loadIndicator;

@synthesize window = _window;
@synthesize webview = _webview;
@synthesize goButton = _goButton;
@synthesize status = _status;
@synthesize statusIndex = _statusIndex;

//@synthesize urls = _urls;
@synthesize articleRefs = _articleRefs;
@synthesize idx = _idx;
@synthesize fdOutput = _fdOutput;
@synthesize progress = _progress;
@synthesize saveLocation = _saveLocation;

- (NSURL *) currentURL
{
    return [NSURL URLWithString:[self.location stringValue]];
}

- (void)applicationDidFinishLaunching:(NSNotification *)aNotification
{
    [self.status setStringValue:@""];
    [self.statusIndex setStringValue:@""];
    [self.location setStringValue:ABSTRACT_ACCEPTED_URL];
    [[self.webview mainFrame] loadRequest:[NSURLRequest requestWithURL:self.currentURL]];
    self.articleRefs = [[NSMutableArray alloc] init];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)theApplication
{
    return YES;
}

- (void)awakeFromNib
{    
    [self.webview setFrameLoadDelegate:self];
    [self.webview setResourceLoadDelegate:self];
}

- (NSArray *)gatherRefs
{
    DOMNodeList *list = [[self.webview.mainFrame DOMDocument] getElementsByClassName:@"AS55"];
    //DOMNodeList *list = [[self.webview.mainFrame DOMDocument] getElementsByName:@"chkArticleListing"];
    NSMutableArray *newURLs = [NSMutableArray arrayWithCapacity:list.length];
    NSURL *base = [NSURL URLWithString:@"http://www.frontiersin.org/"];
    for (int i = 0; i < list.length; i++) {
        
        DOMNode *node = [list item:i];
        DOMNodeList *children = [node childNodes];
        DOMNode *link = nil;
        for (int k = 0; k < children.length; k++) {
            DOMNode *cur = [children item:k];
            NSLog(@"checking %@ ", cur.nodeName);
            if (cur.nodeType == DOM_ELEMENT_NODE &&
                [cur.nodeName compare:@"A"] == NSOrderedSame) {
                link = cur;
                break;
            }
        }

        if (link == nil) {
            NSLog(@"skipping.. ");
            continue;
        }
        DOMNode *attr = [[link attributes] getNamedItem:@"href"];
        NSString *href = [attr nodeValue];
        
        NSURL *url = [NSURL URLWithString:href relativeToURL:base];
       // AFArticleRef *ref = [AFArticleRef refFromCompounedString:val];
        NSLog(@"new URL: %@", url);
        [newURLs addObject:url];
    }
    return newURLs;
}

- (void) startOperation
{
    [self.location setEnabled:NO];
    [self.goButton setEnabled:NO];
    [self.loadIndicator startAnimation:self];
    [self.loadIndicator setHidden:NO];
}

- (void) finishOperation
{
    [self.location setEnabled:YES];
    [self.goButton setEnabled:YES];
    [self.loadIndicator stopAnimation:self];
    [self.loadIndicator setHidden:YES];
}

- (void) showURLs
{
    NSMutableString *str = [[NSMutableString alloc] initWithString:@"<html><body><p>"];
    for (NSURL *ref in self.articleRefs) {
        NSLog(@"%@\n", ref );
        [str appendFormat:@"%@ <br/>", ref];
    }
    [str appendString:@"</p></body></html>"];
    [[self.webview mainFrame] loadHTMLString:str baseURL:[NSURL URLWithString:@"file:///"]];
    
    [self.goButton setTitle:@"Get Abstracts"];
    [self finishOperation];
    state = STATE_HAVE_URLS;
}

- (void) gotoNextPage
{
    NSString *jsString = JS_NEXT_PAGE;
    [self.webview stringByEvaluatingJavaScriptFromString:jsString];
}


- (IBAction)startStop:(NSButton *)sender
{
    if (state == STATE_IDLE) {
       //FIXME changed
   } else if (state == STATE_HAVE_URLS) {
       
        if (self.articleRefs == nil || self.articleRefs.count == 0) {
            return;
        }
        
        NSSavePanel *chooser = [NSSavePanel savePanel];
        
        [chooser beginSheetModalForWindow:self.window completionHandler:^(NSInteger result) {
            if (result == NSFileHandlingPanelOKButton) {
                NSLog(@"%@", chooser.URL.path);
                [self startGetAbstracts:chooser.URL.path];
            }
        }];
   }
}

- (IBAction)gatherURLsNow:(id)sender
{
    if (state == STATE_IDLE) {
        state = STATE_GET_URLS;
    }
    
    //parse and add the new urls
    NSArray *newURLs = [self gatherRefs];
    [self.articleRefs addObjectsFromArray:newURLs];
    [self.status setStringValue:[NSString stringWithFormat:@"Add %lu new URLs [%lu total]",
                                 (unsigned long)newURLs.count,
                                 (unsigned long)self.articleRefs.count]];
    
    if (self.articleRefs.count > 0) {
        state = STATE_HAVE_URLS;
    }
}


- (void)startGetAbstracts:(NSString *)saveLocation
{
    [self startOperation];
    self.saveLocation = saveLocation;

    //hack to make sure that the file exists
    [@"" writeToFile:saveLocation atomically:NO encoding:NSUTF8StringEncoding error:nil];

    NSError *error = nil;
    NSURL *oPath = [NSURL fileURLWithPath:saveLocation];
    NSFileHandle *fh = [NSFileHandle fileHandleForWritingToURL:oPath error:&error];
    if (fh == nil) {
        [self.status setStringValue:[NSString stringWithFormat:@"Error opening output %@!",
                                     [error localizedDescription]]];
        [self finishOperation];
        return;
    }

    [fh truncateFileAtOffset:0];
    self.fdOutput = fh;

    [self.progress setMinValue:0.0];
    [self.progress setMaxValue:[self.articleRefs count]];
    
    self.idx = 0;
    state = STATE_GET_ABS;
    [self processNextUrl];
}

- (void)processNextUrl
{
    NSURL *ref = [self.articleRefs objectAtIndex:self.idx];
    NSUInteger nurls = [self.articleRefs count];
    [self.statusIndex setStringValue:[NSString stringWithFormat:@"%3lu / %3lu", self.idx, nurls]];
    [self.status setStringValue:[ref path]];
    [self.progress setDoubleValue:self.idx];
    [[self.webview mainFrame] loadRequest:[NSURLRequest requestWithURL:ref]];
}

-(void)finishProcessing
{
    [self.fdOutput closeFile];
    self.fdOutput = nil;
    [self.progress setDoubleValue:0];
    [self.status setStringValue:@"All done!"];
    state = STATE_DONE;
    
    NSUInteger nrefs = [self.articleRefs count];
    [self.statusIndex setStringValue:[NSString stringWithFormat:@"%3lu / %3lu", self.idx, nrefs]];
    
    //Display the result file in the main window
    [[self.webview mainFrame] loadRequest:[NSURLRequest requestWithURL:[NSURL fileURLWithPath:self.saveLocation]]];
}

- (void)webView:(WebView *)sender didStartProvisionalLoadForFrame:(WebFrame *)frame
{
    NSLog(@"start Operation: %@", frame.name);
    if (![frame.name isEqualToString:@""]) {
        return;
    }

    [self startOperation];
}

- (void)webView:(WebView *)sender didFinishLoadForFrame:(WebFrame *)frame
{
    if (![frame.name isEqualToString:@""]) {
        return;
    }
 
    NSLog(@"did finsih load for frame!");
    NSString *url = [NSString stringWithFormat:@"%@\n", self.webview.mainFrameURL];
    [self.status setStringValue:url];
    
    [self finishOperation];
    if (state == STATE_GET_URLS) {
        NSLog(@"XXX");
    } else if (state != STATE_GET_ABS)
        return;
    

    NSString *text = [[[self.webview.mainFrame DOMDocument] getElementById:@"col_Mid"] innerText];
    
    [self.fdOutput writeData:[url dataUsingEncoding:NSUTF8StringEncoding]];
    [self.fdOutput writeData:[text dataUsingEncoding:NSUTF8StringEncoding]];
    [self.fdOutput writeData:[@"\n" dataUsingEncoding:NSUTF8StringEncoding]];
    
    self.idx += 1;
    
    if (self.idx < [self.articleRefs count])
        [self processNextUrl];
    else
        [self finishProcessing];
}

- (id)webView:(WebView *)sender identifierForInitialRequest:(NSURLRequest *)request fromDataSource:(WebDataSource *)dataSource
{
    ReqID *rid = [[ReqID alloc] init];
    [self.statusIndex setStringValue:[NSString stringWithFormat:@"%ld", self.idx]];
    if ([request.URL.absoluteString hasPrefix:self.currentURL.absoluteString]) {
        rid.isTarget = YES;
    }
    //NSLog(@"%@ -> %d", request.URL.absoluteString, rid.isTarget);
    return rid;
}

- (void)webView:(WebView *)sender resource:(id)identifier didFinishLoadingFromDataSource:(WebDataSource *)dataSource
{
//    ReqID *rid = identifier;
//   
//    if (!rid.isTarget)
//        return;

//    //parse and add the new urls
//    NSArray *newURLs = [self gatherRefs];
//    [self.articleRefs addObjectsFromArray:newURLs];
//    
//    //find out at which index we currently are
//    NSString *cURL = self.webview.mainFrameURL;
//    NSRange idx = [cURL rangeOfString:@"Index="];
//    if (idx.location == NSNotFound) {
//        [self.status setStringValue:@"ERROR: Could not Find Index="];
//        return;
//    }
//    
//    NSInteger nidx = [[cURL substringFromIndex:(idx.location+6)] integerValue];
//    if (self.idx < nidx) {
//        self.idx = nidx;
//        [self gotoNextPage];
//    }
}

@end
