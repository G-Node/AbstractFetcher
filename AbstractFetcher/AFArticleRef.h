//
//  AFArticleRef.h
//  AbstractFetcher
//
//  Created by Christian Kellner on 8/9/12.
//
//

#import <Foundation/Foundation.h>

@interface AFArticleRef : NSObject
@property (nonatomic, strong) NSString *identifier;
@property (nonatomic, strong) NSString *submissionId;

+ (AFArticleRef *)refWithId:(NSString *)identifier forSubmission:(NSString *)submissionId;
+ (AFArticleRef *)refFromCompounedString:(NSString *)string;
@end
