//
//  AFArticleRef.m
//  AbstractFetcher
//
//  Created by Christian Kellner on 8/9/12.
//
//

#import "AFArticleRef.h"

@implementation AFArticleRef
@synthesize identifier = _identifier;
@synthesize submissionId = _submissionId;


+ (AFArticleRef *)refWithId:(NSString *)identifier forSubmission:(NSString *)submissionId
{
    AFArticleRef *ref = [[AFArticleRef alloc] init];
    
    ref.identifier = identifier;
    ref.submissionId = submissionId;
    
    return  ref;
}

+ (AFArticleRef *)refFromCompounedString:(NSString *)string
{
    string = [string stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    NSArray *components = [string componentsSeparatedByString:@"|"];
    NSString *identifier = [components objectAtIndex:0];
    NSString *submission = [components objectAtIndex:1];
    
    AFArticleRef *ref = [AFArticleRef refWithId:identifier forSubmission:submission];
    return ref;
}
@end
